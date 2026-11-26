"""Lesson history — tenant isolation, trim, stable segments, null timestamps."""

from __future__ import annotations

import uuid

import anyio
from app.db.models import SourceAsset, TranscriptSegment, Video
from app.retrieval import factory as retrieval_factory
from app.services.lesson_history import passage_hash
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


def _video_id(index: int) -> str:
    return f"h{index:010d}"


def _payload(index: int, transcript: str | None = None) -> dict:
    video_id = _video_id(index)
    text = transcript or f"Passage one for {index}.\n\nPassage two for {index}."
    return {
        "youtube_video_id": video_id,
        "title": f"Lesson {index}",
        "channel_title": "Known channel" if index == 1 else None,
        "summary": f"Summary {index}",
        "key_points": [f"Point {index}"],
        "transcript": text,
        "source_url": f"https://www.youtube.com/watch?v={video_id}",
    }


def _save(client: TestClient, index: int, transcript: str | None = None) -> dict:
    response = client.post(
        "/api/v1/learning-history",
        headers=auth_csrf_headers(client),
        json=_payload(index, transcript),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _count_for_video(client: TestClient, video_id: uuid.UUID) -> int:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> int:
        async with session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(TranscriptSegment)
                .where(TranscriptSegment.video_id == video_id)
            )
            return int(result.scalar_one())

    return anyio.run(_run)


def _asset_for_video(client: TestClient, video_id: uuid.UUID) -> tuple[str, str] | None:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> tuple[str, str] | None:
        async with session_factory() as session:
            result = await session.execute(
                select(SourceAsset).where(SourceAsset.video_id == video_id)
            )
            asset = result.scalar_one_or_none()
            if asset is None:
                return None
            return asset.source_kind, asset.storage_key

    return anyio.run(_run)


def test_default_limit_is_ten(client: TestClient) -> None:
    _register(client, "history-default@example.com")
    response = client.get("/api/v1/settings/learning-history")
    assert response.status_code == 200, response.text
    assert response.json()["learning_history_limit"] == 10


def test_save_flags_segments_and_reopen_keeps_ids(client: TestClient) -> None:
    _register(client, "history-reopen@example.com")
    first = _save(client, 1)
    segments = first["segments"]
    # The summary and key points come first as one searchable overview passage.
    expected = [
        "Overview of the video: Summary 1 Key points: Point 1",
        "Passage one for 1.",
        "Passage two for 1.",
    ]
    assert len(segments) == 3
    assert first["source_kind"] == "gemini_youtube"
    assert first["created"] is True
    ids = [row["id"] for row in segments]
    for row, text in zip(segments, expected, strict=True):
        assert row["text"] == text
        assert row["start_ms"] is None
        assert row["end_ms"] is None
        assert row["evidence_origin"] == "video_transcript"
        assert row["evidence_provider"] == "gemini_youtube"
        assert row["source_kind"] == "gemini_youtube"
        assert row["content_hash"] == passage_hash(text)

    video_id = uuid.UUID(first["video"]["id"])
    asset = _asset_for_video(client, video_id)
    assert asset is not None
    source_kind, storage_key = asset
    assert source_kind == "gemini_youtube"
    assert storage_key.startswith("gemini-youtube/")
    assert "://" not in storage_key

    second = _save(client, 1, transcript="Passage one for 1.\n\nPassage two for 1.")
    assert second["created"] is False
    assert second["video"]["id"] == first["video"]["id"]
    assert [row["id"] for row in second["segments"]] == ids
    assert all(row["start_ms"] is None and row["end_ms"] is None for row in second["segments"])

    opened = client.post(
        f"/api/v1/learning-history/{video_id}/open",
        headers=auth_csrf_headers(client),
    )
    assert opened.status_code == 200, opened.text
    assert [row["id"] for row in opened.json()["segments"]] == ids

    changed = _save(client, 1, transcript="Only one new passage.")
    assert [row["id"] for row in changed["segments"]] != ids
    assert changed["segments"][0]["start_ms"] is None
    assert retrieval_factory._MEMORY_STORE is None


def test_eleventh_lesson_drops_oldest_segments(client: TestClient) -> None:
    _register(client, "history-trim@example.com")
    saved = [_save(client, index) for index in range(1, 12)]
    oldest = uuid.UUID(saved[0]["video"]["id"])
    newest = saved[-1]["video"]["id"]

    listed = client.get("/api/v1/learning-history")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["learning_history_limit"] == 10
    assert len(body["items"]) == 10
    assert body["items"][0]["id"] == newest
    assert all(item["id"] != str(oldest) for item in body["items"])
    assert _count_for_video(client, oldest) == 0

    missing = client.get(f"/api/v1/learning-history/{oldest}")
    assert missing.status_code == 404
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _video_gone() -> Video | None:
        async with session_factory() as session:
            return await session.get(Video, oldest)

    assert anyio.run(_video_gone) is None


def test_setting_limit_to_three_keeps_three(client: TestClient) -> None:
    _register(client, "history-three@example.com")
    saved = [_save(client, index) for index in range(1, 5)]
    updated = client.put(
        "/api/v1/settings/learning-history",
        headers=auth_csrf_headers(client),
        json={"learning_history_limit": 3},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["learning_history_limit"] == 3

    listed = client.get("/api/v1/learning-history")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 3
    assert [item["id"] for item in items] == [
        saved[3]["video"]["id"],
        saved[2]["video"]["id"],
        saved[1]["video"]["id"],
    ]
    dropped = uuid.UUID(saved[0]["video"]["id"])
    assert _count_for_video(client, dropped) == 0

    rejected = client.put(
        "/api/v1/settings/learning-history",
        headers=auth_csrf_headers(client),
        json={"learning_history_limit": 0},
    )
    assert rejected.status_code == 422


def test_other_workspace_cannot_read_lesson_or_segments(client: TestClient) -> None:
    owner = _register(client, "history-a@example.com")
    saved = _save(client, 7)
    video_id = saved["video"]["id"]
    segment_ids = [row["id"] for row in saved["segments"]]
    headers_a = auth_csrf_headers(client)
    client.post("/api/v1/auth/logout", headers=headers_a)

    _register(client, "history-b@example.com")
    foreign = client.get(f"/api/v1/learning-history/{video_id}")
    assert foreign.status_code == 404
    foreign_open = client.post(
        f"/api/v1/learning-history/{video_id}/open",
        headers=auth_csrf_headers(client),
    )
    assert foreign_open.status_code == 404
    listed = client.get("/api/v1/learning-history")
    assert listed.status_code == 200
    assert listed.json()["items"] == []

    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory
    workspace_b = uuid.UUID(client.get("/api/v1/me").json()["workspace"]["id"])
    workspace_a = uuid.UUID(owner["workspace"]["id"])

    async def _counts() -> tuple[int, int]:
        async with session_factory() as session:
            owned = await session.execute(
                select(func.count())
                .select_from(TranscriptSegment)
                .where(
                    TranscriptSegment.workspace_id == workspace_a,
                    TranscriptSegment.id.in_([uuid.UUID(item) for item in segment_ids]),
                )
            )
            leaked = await session.execute(
                select(func.count())
                .select_from(TranscriptSegment)
                .where(TranscriptSegment.workspace_id == workspace_b)
            )
            return int(owned.scalar_one()), int(leaked.scalar_one())

    owned_count, leaked_count = anyio.run(_counts)
    assert owned_count == len(segment_ids)
    assert leaked_count == 0
