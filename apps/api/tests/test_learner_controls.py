"""Pin, trim, and remove for one workspace's Gemini lessons."""

from __future__ import annotations

import uuid

import anyio
from app.db.models import ChatMessage, ChatThread, ExternalEvidence, TranscriptSegment
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Learner"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _save(client: TestClient, index: int) -> dict:
    video_id = f"p{index:010d}"
    response = client.post(
        "/api/v1/learning-history",
        headers=auth_csrf_headers(client),
        json={
            "youtube_video_id": video_id,
            "title": f"Lesson {index}",
            "channel_title": None,
            "summary": f"Summary {index}",
            "key_points": [f"Point {index}"],
            "transcript": f"Passage one for {index}.\n\nPassage two for {index}.",
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _counts(client: TestClient, video_id: uuid.UUID) -> tuple[int, int, int]:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> tuple[int, int, int]:
        async with session_factory() as session:
            segments = await session.execute(
                select(func.count())
                .select_from(TranscriptSegment)
                .where(TranscriptSegment.video_id == video_id)
            )
            threads = await session.execute(
                select(func.count())
                .select_from(ChatThread)
                .where(ChatThread.scope_kind == "video", ChatThread.scope_id == video_id)
            )
            evidence = await session.execute(
                select(func.count())
                .select_from(ExternalEvidence)
                .where(ExternalEvidence.video_id == video_id)
            )
            return (
                int(segments.scalar_one()),
                int(threads.scalar_one()),
                int(evidence.scalar_one()),
            )

    return anyio.run(_run)


def _attach_thread(client: TestClient, *, workspace_id: str, user_id: str, video_id: str) -> None:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> None:
        async with session_factory() as session:
            thread = ChatThread(
                workspace_id=uuid.UUID(workspace_id),
                scope_kind="video",
                scope_id=uuid.UUID(video_id),
                title="Ask AI",
                created_by=uuid.UUID(user_id),
            )
            session.add(thread)
            await session.flush()
            message = ChatMessage(
                thread_id=thread.id,
                workspace_id=uuid.UUID(workspace_id),
                role="user",
                content="Why?",
                unsupported=False,
            )
            session.add(message)
            await session.flush()
            session.add(
                ExternalEvidence(
                    workspace_id=uuid.UUID(workspace_id),
                    video_id=uuid.UUID(video_id),
                    thread_id=thread.id,
                    message_id=message.id,
                    evidence_origin="external_search",
                    evidence_provider="openalex",
                    title="Paper",
                    source_url="https://example.edu/paper",
                    snippet="A kept snippet",
                    content_hash="abc123",
                )
            )
            await session.commit()

    anyio.run(_run)


def test_pin_survives_trim_and_unpin_then_deletes(client: TestClient) -> None:
    owner = _register(client, "pin-trim@example.com")
    oldest = _save(client, 1)
    pinned = _save(client, 2)
    newest = _save(client, 3)
    oldest_id = oldest["video"]["id"]
    pinned_id = pinned["video"]["id"]
    newest_id = newest["video"]["id"]
    _attach_thread(
        client,
        workspace_id=owner["workspace"]["id"],
        user_id=owner["user"]["id"],
        video_id=oldest_id,
    )
    _attach_thread(
        client,
        workspace_id=owner["workspace"]["id"],
        user_id=owner["user"]["id"],
        video_id=pinned_id,
    )

    pin = client.put(
        f"/api/v1/learning-history/{pinned_id}/pin",
        headers=auth_csrf_headers(client),
        json={"pinned": True},
    )
    assert pin.status_code == 200, pin.text
    assert pin.json()["pinned"] is True

    limited = client.put(
        "/api/v1/settings/learning-history",
        headers=auth_csrf_headers(client),
        json={"learning_history_limit": 1},
    )
    assert limited.status_code == 200, limited.text

    listed = client.get("/api/v1/learning-history")
    assert listed.status_code == 200, listed.text
    kept = {item["id"] for item in listed.json()["items"]}
    assert kept == {pinned_id, newest_id}
    assert _counts(client, uuid.UUID(oldest_id)) == (0, 0, 0)
    assert _counts(client, uuid.UUID(pinned_id))[0] == 2

    unpin = client.put(
        f"/api/v1/learning-history/{pinned_id}/pin",
        headers=auth_csrf_headers(client),
        json={"pinned": False},
    )
    assert unpin.status_code == 200, unpin.text
    assert unpin.json()["pinned"] is False
    # Unpinning alone keeps the row; the next trim drops the oldest unpinned lesson.
    assert _counts(client, uuid.UUID(pinned_id))[0] == 2

    retrim = client.put(
        "/api/v1/settings/learning-history",
        headers=auth_csrf_headers(client),
        json={"learning_history_limit": 1},
    )
    assert retrim.status_code == 200, retrim.text
    assert _counts(client, uuid.UUID(pinned_id)) == (0, 0, 0)
    still = client.get("/api/v1/learning-history")
    assert [item["id"] for item in still.json()["items"]] == [newest_id]


def test_remove_clears_segments_and_thread(client: TestClient) -> None:
    owner = _register(client, "remove-lesson@example.com")
    saved = _save(client, 4)
    video_id = saved["video"]["id"]
    _attach_thread(
        client,
        workspace_id=owner["workspace"]["id"],
        user_id=owner["user"]["id"],
        video_id=video_id,
    )
    assert _counts(client, uuid.UUID(video_id)) == (2, 1, 1)

    removed = client.delete(
        f"/api/v1/learning-history/{video_id}",
        headers=auth_csrf_headers(client),
    )
    assert removed.status_code == 204, removed.text
    assert _counts(client, uuid.UUID(video_id)) == (0, 0, 0)
    missing = client.get(f"/api/v1/learning-history/{video_id}")
    assert missing.status_code == 404


def test_other_workspace_cannot_remove_or_pin(client: TestClient) -> None:
    _register(client, "pin-owner@example.com")
    saved = _save(client, 5)
    video_id = saved["video"]["id"]
    client.post("/api/v1/auth/logout", headers=auth_csrf_headers(client))

    _register(client, "pin-other@example.com")
    headers = auth_csrf_headers(client)
    removed = client.delete(f"/api/v1/learning-history/{video_id}", headers=headers)
    assert removed.status_code == 404
    assert removed.json()["error"]["code"] == "LESSON_NOT_IN_WORKSPACE"
    pinned = client.put(
        f"/api/v1/learning-history/{video_id}/pin",
        headers=headers,
        json={"pinned": True},
    )
    assert pinned.status_code == 404
    assert pinned.json()["error"]["code"] == "LESSON_NOT_IN_WORKSPACE"

    client.post("/api/v1/auth/logout", headers=headers)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "pin-owner@example.com", "password": "correct-horse-1"},
    )
    assert login.status_code == 200, login.text
    still = client.get(f"/api/v1/learning-history/{video_id}")
    assert still.status_code == 200, still.text
    assert still.json()["video"]["pinned"] is False
    assert _counts(client, uuid.UUID(video_id))[0] == 2
