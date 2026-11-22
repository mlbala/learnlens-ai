"""Trim both origins, cache the lesson body only, and keep the usage line redacted."""

from __future__ import annotations

import json
import uuid

import anyio
from app.core.settings import Settings
from app.db.models import ChatThread, ExternalEvidence, TranscriptSegment
from app.retrieval.contracts import ChunkIndexRecord
from app.retrieval.factory import build_vector_store
from app.retrieval.profile import active_embedding_profile, collection_name_for
from app.retrieval.session_lanes import ORIGIN_EXTERNAL, ORIGIN_VIDEO
from app.services.answer_usage import answer_usage_line
from app.services.lesson_cache import lesson_body_cache_payload, read_lesson_body
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers


class FailingLessonCache:
    def get(self, key: str) -> dict | None:
        raise ConnectionError(f"redis down for {key}")

    def put(self, key: str, payload: dict) -> None:
        raise ConnectionError(f"redis down for {key} {len(payload)}")

    def delete_prefix(self, prefix: str) -> None:
        raise ConnectionError(f"redis down for {prefix}")


def test_cache_payload_omits_outside_snippet() -> None:
    snippet = "Tavily snippet UNIQUE_OUTSIDE about tides https://example.com/search?q=secret"
    payload = lesson_body_cache_payload(
        {
            "summary": "Tides follow the moon.",
            "key_points": ["Moon"],
            "segments": [
                {
                    "id": str(uuid.uuid4()),
                    "ordinal": 1,
                    "text": "The moon pulls the sea.",
                    "content_hash": "abc",
                    "snippet": snippet,
                }
            ],
            "snippet": snippet,
            "external_evidence": [
                {
                    "snippet": snippet,
                    "title": "Tide paper",
                    "source_url": "https://example.com/search?q=secret",
                }
            ],
            "qdrant_hits": [{"text": snippet}],
        }
    )
    encoded = json.dumps(payload)
    assert snippet not in encoded
    assert "Tide paper" not in encoded
    assert "q=secret" not in encoded
    assert payload["summary"] == "Tides follow the moon."
    assert payload["segments"][0]["text"] == "The moon pulls the sea."
    assert "snippet" not in payload["segments"][0]


def test_redis_down_reads_neon() -> None:
    body = read_lesson_body(
        FailingLessonCache(),
        "ll:lesson-body:workspace:video:hash",
        lambda: {
            "summary": "From neon",
            "key_points": ["One"],
            "segments": [],
            "snippet": "Tavily snippet that must not be cached",
        },
    )
    assert body["summary"] == "From neon"
    assert "snippet" not in body
    assert "Tavily snippet" not in json.dumps(body)


def test_usage_line_has_counts_not_transcript_or_snippet() -> None:
    transcript = "UNIQUE_TRANSCRIPT_SENTENCE about quarks in the lesson body"
    snippet = "UNIQUE_TAVILY_SNIPPET from the search result"
    title = "UNIQUE_SOURCE_TITLE"
    url = "https://example.com/search?q=UNIQUE_QUERY"
    line = answer_usage_line(
        workspace_id=uuid.uuid4(),
        video_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        decision="blend",
        review_status="accepted",
        external_search_enabled=True,
        kept_video_passages=2,
        kept_outside_passages=1,
        input_tokens=11,
        output_tokens=7,
        transcript=transcript,
        snippet=snippet,
        source_title=title,
        source_url=url,
    )
    record = json.loads(line)
    assert record["kept_video_passages"] == 2
    assert record["kept_outside_passages"] == 1
    assert record["input_tokens"] == 11
    assert record["external_search_enabled"] is True
    assert transcript not in line
    assert snippet not in line
    assert title not in line
    assert "UNIQUE_QUERY" not in line
    assert "http" not in line


def test_delete_by_video_removes_both_origins(settings: Settings) -> None:
    profile = active_embedding_profile(settings)
    store = build_vector_store(settings)
    collection = store.ensure_collection(
        profile_id=profile.profile_id,
        dimensions=profile.dimensions,
    )
    workspace_a = uuid.uuid4()
    workspace_b = uuid.uuid4()
    video_a = uuid.uuid4()
    video_b = uuid.uuid4()
    thread_id = uuid.uuid4()
    vector = [0.1] * profile.dimensions
    records = [
        _record(
            workspace_id=workspace_a,
            video_id=video_a,
            thread_id=thread_id,
            origin=ORIGIN_VIDEO,
            text="Video passage about tides.",
            vector=vector,
        ),
        _record(
            workspace_id=workspace_a,
            video_id=video_a,
            thread_id=thread_id,
            origin=ORIGIN_EXTERNAL,
            text="Outside snippet about tides.",
            vector=vector,
        ),
        _record(
            workspace_id=workspace_b,
            video_id=video_b,
            thread_id=uuid.uuid4(),
            origin=ORIGIN_VIDEO,
            text="Other workspace passage.",
            vector=vector,
        ),
    ]
    store.upsert_chunks(
        collection=collection,
        profile_id=profile.profile_id,
        dimensions=profile.dimensions,
        records=records,
    )
    removed = store.delete_by_video(
        collection=collection,
        workspace_id=workspace_a,
        video_id=video_a,
    )
    assert removed == 2
    assert _origins(store, collection, video_a) == set()
    assert _origins(store, collection, video_b) == {ORIGIN_VIDEO}


def test_trim_to_two_drops_both_origins_and_hides_the_other_workspace(client: TestClient) -> None:
    _register(client, "fit-a@example.com")
    oldest = _save(client, "Older lesson passage about tides.")
    _retrieve(
        client,
        oldest["video"]["id"],
        "What do tides do?",
        sources=[
            {
                "title": "Tide paper",
                "url": "https://doi.org/10.1000/tides",
                "snippet": "Tides follow the moon.",
                "kind": "paper",
                "provider": "openalex",
            }
        ],
    )
    assert _thread_count(client, oldest["video"]["id"]) == 1
    assert _origins_for(client, oldest["video"]["id"]) == {ORIGIN_VIDEO, ORIGIN_EXTERNAL}
    second = _save(client, "Second lesson passage about comets.")
    third = _save(client, "Third lesson passage about dunes.")
    limited = client.put(
        "/api/v1/settings/learning-history",
        headers=auth_csrf_headers(client),
        json={"learning_history_limit": 2},
    )
    assert limited.status_code == 200, limited.text
    listed = client.get("/api/v1/learning-history")
    assert listed.status_code == 200, listed.text
    ids = {item["id"] for item in listed.json()["items"]}
    assert ids == {second["video"]["id"], third["video"]["id"]}
    assert oldest["video"]["id"] not in ids
    assert _segment_count(client, oldest["video"]["id"]) == 0
    assert _evidence_count(client, oldest["video"]["id"]) == 0
    assert _thread_count(client, oldest["video"]["id"]) == 0
    assert _origins_for(client, oldest["video"]["id"]) == set()

    _register(client, "fit-b@example.com")
    foreign = client.get("/api/v1/learning-history")
    assert foreign.status_code == 200, foreign.text
    foreign_ids = {item["id"] for item in foreign.json()["items"]}
    assert second["video"]["id"] not in foreign_ids
    opened = client.get(f"/api/v1/learning-history/{second['video']['id']}")
    assert opened.status_code == 404
    assert opened.json()["error"]["message"] == "This lesson is not in this workspace."


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Learner"},
    )
    assert response.status_code == 201, response.text


def _save(client: TestClient, transcript: str) -> dict:
    video_id = uuid.uuid4().hex[:11]
    response = client.post(
        "/api/v1/learning-history",
        headers=auth_csrf_headers(client),
        json={
            "youtube_video_id": video_id,
            "title": "Lesson",
            "channel_title": "Known channel",
            "summary": "Summary",
            "key_points": ["Point"],
            "transcript": transcript,
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _retrieve(
    client: TestClient,
    video_id: str,
    question: str,
    sources: list[dict[str, str]],
) -> None:
    response = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/retrieve",
        headers=auth_csrf_headers(client),
        json={"question": question, "external_search": True, "sources": sources},
    )
    assert response.status_code == 200, response.text


def _count(client: TestClient, model: type, video_id: str) -> int:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> int:
        async with session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(model).where(model.video_id == uuid.UUID(video_id))
            )
            return int(result.scalar_one())

    return anyio.run(_run)


def _segment_count(client: TestClient, video_id: str) -> int:
    return _count(client, TranscriptSegment, video_id)


def _evidence_count(client: TestClient, video_id: str) -> int:
    return _count(client, ExternalEvidence, video_id)


def _thread_count(client: TestClient, video_id: str) -> int:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> int:
        async with session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(ChatThread)
                .where(ChatThread.scope_id == uuid.UUID(video_id))
            )
            return int(result.scalar_one())

    return anyio.run(_run)


def _origins_for(client: TestClient, video_id: str) -> set[str]:
    settings: Settings = client.app.state.settings
    profile = active_embedding_profile(settings)
    store = build_vector_store(settings)
    collection = collection_name_for(profile.profile_id)
    return _origins(store, collection, uuid.UUID(video_id))


def _origins(store: object, collection: str, video_id: uuid.UUID) -> set[str]:
    points = store._collections.get(collection)  # type: ignore[attr-defined]  # noqa: SLF001
    if points is None:
        return set()
    return {
        str(data["payload"].get("evidence_origin"))
        for data in points.points.values()
        if data["payload"].get("video_id") == str(video_id)
    }


def _record(
    *,
    workspace_id: uuid.UUID,
    video_id: uuid.UUID,
    thread_id: uuid.UUID,
    origin: str,
    text: str,
    vector: list[float],
) -> ChunkIndexRecord:
    return ChunkIndexRecord(
        chunk_id=uuid.uuid4(),
        workspace_id=workspace_id,
        video_id=video_id,
        source_asset_id=uuid.uuid4(),
        source_revision=1,
        segment_ids=(uuid.uuid4(),) if origin == ORIGIN_VIDEO else (),
        text=text,
        dense_vector=vector,
        content_hash=uuid.uuid4().hex,
        evidence_origin=origin,
        evidence_provider="gemini_youtube" if origin == ORIGIN_VIDEO else "tavily",
        thread_id=thread_id,
        source_url="https://example.test/source",
    )
