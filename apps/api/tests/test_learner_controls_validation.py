"""Validation and evidence-contract checks for lesson Pin and Remove.

Covers request validation (auth, CSRF, body, path), the full per-video delete
sequence (chapters, citations, source asset, Redis key, Qdrant points), and
workspace isolation when two workspaces saved the same YouTube video.
"""

from __future__ import annotations

import uuid
from typing import Any

import anyio
import pytest
from app.db.models import (
    Chapter,
    ChatMessage,
    ChatThread,
    ExternalEvidence,
    MessageCitation,
    SourceAsset,
    TranscriptSegment,
    Video,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers

PASSWORD = "correct-horse-1"


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "name": "Learner"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str) -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text


def _logout(client: TestClient) -> None:
    client.post("/api/v1/auth/logout", headers=auth_csrf_headers(client))


def _save(client: TestClient, video_id: str, title: str | None = None) -> dict:
    response = client.post(
        "/api/v1/learning-history",
        headers=auth_csrf_headers(client),
        json={
            "youtube_video_id": video_id,
            "title": title or f"Lesson {video_id}",
            "channel_title": None,
            "summary": "Summary",
            "key_points": ["Point"],
            "transcript": "Passage one.\n\nPassage two.",
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _pin(client: TestClient, video_id: str, pinned: Any, **extra: Any):
    return client.put(
        f"/api/v1/learning-history/{video_id}/pin",
        headers=auth_csrf_headers(client),
        json={"pinned": pinned, **extra},
    )


def _limit(client: TestClient, value: int) -> None:
    response = client.put(
        "/api/v1/settings/learning-history",
        headers=auth_csrf_headers(client),
        json={"learning_history_limit": value},
    )
    assert response.status_code == 200, response.text


def _listed(client: TestClient) -> list[str]:
    response = client.get("/api/v1/learning-history")
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def _sessions(client: TestClient) -> async_sessionmaker[AsyncSession]:
    return client.app.state.session_factory


def _count(client: TestClient, model: Any, video_id: str) -> int:
    async def _run() -> int:
        async with _sessions(client)() as session:
            column = model.id if model is Video else model.video_id
            result = await session.execute(
                select(func.count()).select_from(model).where(column == uuid.UUID(video_id))
            )
            return int(result.scalar_one())

    return anyio.run(_run)


def _seed_chat_evidence(client: TestClient, owner: dict, video_id: str) -> None:
    """One thread, message, citation, external row, and chapter for a saved lesson."""
    workspace_id = uuid.UUID(owner["workspace"]["id"])
    user_id = uuid.UUID(owner["user"]["id"])
    vid = uuid.UUID(video_id)

    async def _run() -> None:
        async with _sessions(client)() as session:
            segment = (
                await session.execute(
                    select(TranscriptSegment)
                    .where(TranscriptSegment.video_id == vid)
                    .order_by(TranscriptSegment.ordinal)
                    .limit(1)
                )
            ).scalar_one()
            thread = ChatThread(
                workspace_id=workspace_id,
                scope_kind="video",
                scope_id=vid,
                title="Ask AI",
                created_by=user_id,
            )
            session.add(thread)
            await session.flush()
            message = ChatMessage(
                thread_id=thread.id,
                workspace_id=workspace_id,
                role="assistant",
                content="Because.",
                unsupported=False,
            )
            session.add(message)
            await session.flush()
            session.add(
                MessageCitation(
                    message_id=message.id,
                    workspace_id=workspace_id,
                    segment_id=segment.id,
                    video_id=vid,
                    citation_key="S1",
                    snippet="Passage one.",
                )
            )
            session.add(
                ExternalEvidence(
                    workspace_id=workspace_id,
                    video_id=vid,
                    thread_id=thread.id,
                    message_id=message.id,
                    evidence_origin="external_search",
                    evidence_provider="openalex",
                    title="Paper",
                    source_url="https://example.edu/paper",
                    snippet="Kept snippet",
                    content_hash="hash-1",
                )
            )
            session.add(
                Chapter(
                    video_id=vid,
                    workspace_id=workspace_id,
                    title="Intro",
                    start_segment_id=segment.id,
                    end_segment_id=segment.id,
                )
            )
            await session.commit()

    anyio.run(_run)


# --- Request validation ------------------------------------------------------


def test_pin_and_remove_require_sign_in(client: TestClient) -> None:
    video_id = str(uuid.uuid4())
    assert client.delete(f"/api/v1/learning-history/{video_id}").status_code == 401
    pinned = client.put(f"/api/v1/learning-history/{video_id}/pin", json={"pinned": True})
    assert pinned.status_code == 401


def test_pin_and_remove_require_csrf(client: TestClient) -> None:
    _register(client, "csrf-controls@example.com")
    saved = _save(client, "c0000000001")
    video_id = saved["video"]["id"]

    removed = client.delete(f"/api/v1/learning-history/{video_id}")
    assert removed.status_code == 403
    assert removed.json()["error"]["code"] == "CSRF_FAILED"
    pinned = client.put(f"/api/v1/learning-history/{video_id}/pin", json={"pinned": True})
    assert pinned.status_code == 403
    assert pinned.json()["error"]["code"] == "CSRF_FAILED"
    # Nothing changed.
    assert _listed(client) == [video_id]
    assert _count(client, TranscriptSegment, video_id) == 2


@pytest.mark.parametrize(
    "body",
    [
        {"pinned": "yes"},
        {"pinned": "true"},
        {"pinned": 1},
        {"pinned": None},
        {},
        {"pinned": True, "start_ms": 0},
    ],
)
def test_pin_body_accepts_only_json_booleans(client: TestClient, body: dict) -> None:
    _register(client, f"pin-body-{uuid.uuid4().hex[:8]}@example.com")
    saved = _save(client, "b0000000001")
    video_id = saved["video"]["id"]
    response = client.put(
        f"/api/v1/learning-history/{video_id}/pin",
        headers=auth_csrf_headers(client),
        json=body,
    )
    assert response.status_code == 422, response.text
    detail = client.get(f"/api/v1/learning-history/{video_id}")
    assert detail.json()["video"]["pinned"] is False


def test_bad_video_id_is_rejected(client: TestClient) -> None:
    _register(client, "bad-id@example.com")
    headers = auth_csrf_headers(client)
    assert client.delete("/api/v1/learning-history/not-a-uuid", headers=headers).status_code == 422
    pinned = client.put(
        "/api/v1/learning-history/not-a-uuid/pin", headers=headers, json={"pinned": True}
    )
    assert pinned.status_code == 422


def test_unknown_lesson_is_404(client: TestClient) -> None:
    _register(client, "unknown-lesson@example.com")
    missing = str(uuid.uuid4())
    removed = client.delete(
        f"/api/v1/learning-history/{missing}", headers=auth_csrf_headers(client)
    )
    assert removed.status_code == 404
    assert removed.json()["error"]["code"] == "LESSON_NOT_IN_WORKSPACE"
    pinned = _pin(client, missing, True)
    assert pinned.status_code == 404
    assert pinned.json()["error"]["code"] == "LESSON_NOT_IN_WORKSPACE"


# --- Pin state -----------------------------------------------------------------


def test_pin_is_reported_by_list_detail_and_videos_api(client: TestClient) -> None:
    _register(client, "pin-report@example.com")
    saved = _save(client, "r0000000001")
    video_id = saved["video"]["id"]
    assert _pin(client, video_id, True).json() == {"video_id": video_id, "pinned": True}

    items = client.get("/api/v1/learning-history").json()["items"]
    assert items[0]["pinned"] is True
    assert client.get(f"/api/v1/learning-history/{video_id}").json()["video"]["pinned"] is True
    assert client.get(f"/api/v1/videos/{video_id}").json()["pinned"] is True

    # Pinning twice is idempotent.
    assert _pin(client, video_id, True).status_code == 200
    assert _pin(client, video_id, False).json()["pinned"] is False


def test_pinned_lessons_do_not_count_toward_the_limit(client: TestClient) -> None:
    _register(client, "pin-limit@example.com")
    first = _save(client, "l0000000001")["video"]["id"]
    second = _save(client, "l0000000002")["video"]["id"]
    assert _pin(client, first, True).status_code == 200
    assert _pin(client, second, True).status_code == 200
    _limit(client, 1)

    third = _save(client, "l0000000003")["video"]["id"]
    assert set(_listed(client)) == {first, second, third}

    fourth = _save(client, "l0000000004")["video"]["id"]
    kept = set(_listed(client))
    assert kept == {first, second, fourth}
    assert _count(client, Video, third) == 0
    assert _count(client, TranscriptSegment, third) == 0


def test_unpin_alone_does_not_delete(client: TestClient) -> None:
    _register(client, "unpin-keeps@example.com")
    old = _save(client, "u0000000001")["video"]["id"]
    _pin(client, old, True)
    new = _save(client, "u0000000002")["video"]["id"]
    _limit(client, 1)
    assert set(_listed(client)) == {old, new}

    assert _pin(client, old, False).status_code == 200
    assert set(_listed(client)) == {old, new}

    # Opening the newer lesson runs trim, which drops the oldest unpinned one.
    opened = client.post(
        f"/api/v1/learning-history/{new}/open", headers=auth_csrf_headers(client)
    )
    assert opened.status_code == 200, opened.text
    assert _listed(client) == [new]
    assert _count(client, Video, old) == 0


# --- Remove --------------------------------------------------------------------


class RecordingCache:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def get(self, key: str) -> dict | None:
        return None

    def put(self, key: str, payload: dict) -> None:
        return None

    def delete_prefix(self, prefix: str) -> None:
        self.deleted.append(prefix)


class RecordingStore:
    def __init__(self) -> None:
        self.deleted: list[tuple[uuid.UUID, uuid.UUID]] = []

    def ensure_collection(self, *, profile_id: str, dimensions: int) -> str:
        return f"{profile_id}-{dimensions}"

    def delete_by_video(
        self, *, collection: str, workspace_id: uuid.UUID, video_id: uuid.UUID, **_: Any
    ) -> None:
        self.deleted.append((workspace_id, video_id))


def test_remove_deletes_the_whole_evidence_contract(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = RecordingCache()
    store = RecordingStore()
    monkeypatch.setattr(
        "app.api.v1.learning_history.lesson_cache_from_settings", lambda _settings: cache
    )
    monkeypatch.setattr("app.retrieval.factory.build_vector_store", lambda _settings: store)

    owner = _register(client, "remove-contract@example.com")
    saved = _save(client, "x0000000001")
    video_id = saved["video"]["id"]
    _seed_chat_evidence(client, owner, video_id)
    for model in (Chapter, MessageCitation, ExternalEvidence, SourceAsset):
        assert _count(client, model, video_id) == 1, model.__name__
    cache.deleted.clear()

    removed = client.delete(
        f"/api/v1/learning-history/{video_id}", headers=auth_csrf_headers(client)
    )
    assert removed.status_code == 204, removed.text
    assert removed.content == b""

    for model in (
        Video,
        SourceAsset,
        TranscriptSegment,
        Chapter,
        MessageCitation,
        ExternalEvidence,
    ):
        assert _count(client, model, video_id) == 0, model.__name__

    async def _threads() -> int:
        async with _sessions(client)() as session:
            result = await session.execute(
                select(func.count())
                .select_from(ChatThread)
                .where(ChatThread.scope_id == uuid.UUID(video_id))
            )
            return int(result.scalar_one())

    assert anyio.run(_threads) == 0
    workspace_id = owner["workspace"]["id"]
    assert cache.deleted == [f"ll:lesson-body:{workspace_id}:{video_id}:"]
    assert store.deleted == [(uuid.UUID(workspace_id), uuid.UUID(video_id))]

    again = client.delete(
        f"/api/v1/learning-history/{video_id}", headers=auth_csrf_headers(client)
    )
    assert again.status_code == 404


def test_remove_only_touches_the_callers_workspace(client: TestClient) -> None:
    shared_youtube_id = "s0000000001"
    first = _register(client, "same-video-a@example.com")
    first_video = _save(client, shared_youtube_id)["video"]["id"]
    _seed_chat_evidence(client, first, first_video)
    _logout(client)

    _register(client, "same-video-b@example.com")
    second_video = _save(client, shared_youtube_id)["video"]["id"]
    assert second_video != first_video
    removed = client.delete(
        f"/api/v1/learning-history/{second_video}", headers=auth_csrf_headers(client)
    )
    assert removed.status_code == 204
    _logout(client)

    _login(client, "same-video-a@example.com")
    assert _listed(client) == [first_video]
    assert _count(client, TranscriptSegment, first_video) == 2
    assert _count(client, ExternalEvidence, first_video) == 1
    assert _count(client, MessageCitation, first_video) == 1


def test_remove_refuses_a_video_that_is_not_a_gemini_lesson(client: TestClient) -> None:
    owner = _register(client, "not-a-lesson@example.com")
    workspace_id = uuid.UUID(owner["workspace"]["id"])

    async def _insert() -> str:
        async with _sessions(client)() as session:
            video = Video(
                workspace_id=workspace_id,
                youtube_video_id="n0000000001",
                title="Uploaded transcript video",
                status="ready",
                metadata_json={"transcript_access": True},
            )
            session.add(video)
            await session.commit()
            return str(video.id)

    video_id = anyio.run(_insert)
    removed = client.delete(
        f"/api/v1/learning-history/{video_id}", headers=auth_csrf_headers(client)
    )
    assert removed.status_code == 404
    assert removed.json()["error"]["code"] == "LESSON_NOT_IN_WORKSPACE"
    assert _pin(client, video_id, True).status_code == 404
    assert _count(client, Video, video_id) == 1
