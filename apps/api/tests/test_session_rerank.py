"""Session lanes: decision, origin filter, lexical fallback, and idempotent points."""

from __future__ import annotations

import uuid

import anyio
import pytest
from app.core.settings import Settings
from app.db.models import ExternalEvidence, TranscriptSegment
from app.retrieval.contracts import ChunkIndexRecord
from app.retrieval.factory import build_vector_store
from app.retrieval.filters import build_tenant_scope, payload_matches_scope
from app.retrieval.profile import active_embedding_profile, collection_name_for
from app.retrieval.qdrant_store import PAYLOAD_INDEX_FIELDS
from app.retrieval.session_lanes import (
    ORIGIN_EXTERNAL,
    ORIGIN_VIDEO,
    LanePassage,
    decide,
    lexical_score,
    rank_lane,
)
from app.retrieval.thresholds import VIDEO_COVERAGE_THRESHOLD
from app.services.session_evidence import OriginPoint, index_origin_points
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers

PAPER_URL = "https://doi.org/10.1000/quasar-note"
OUTSIDE = "A journal note about distant quasars and radio surveys."
GLUCOSE_LESSON = (
    "Photosynthesis converts sunlight into glucose in leaves.\n\n"
    "The Roman senate debated grain subsidies."
)


def test_decision_table_covers_each_lane_outcome() -> None:
    high = VIDEO_COVERAGE_THRESHOLD
    low = VIDEO_COVERAGE_THRESHOLD - 0.01
    assert decide(external_search=False, best_video_score=high, external_kept=3) == "lesson_only"
    assert decide(external_search=False, best_video_score=low, external_kept=3) == "abstain"
    assert decide(external_search=True, best_video_score=high, external_kept=2) == "blend"
    assert decide(external_search=True, best_video_score=low, external_kept=1) == "blend"
    assert decide(external_search=True, best_video_score=high, external_kept=0) == "lesson_only"
    assert decide(external_search=True, best_video_score=low, external_kept=0) == "abstain"


def test_origin_filter_drops_other_lanes_and_blank_origins(settings: Settings) -> None:
    store = build_vector_store(settings)
    profile = active_embedding_profile(settings)
    collection = store.ensure_collection(
        profile_id=profile.profile_id,
        dimensions=profile.dimensions,
    )
    workspace_id = uuid.uuid4()
    video_id = uuid.uuid4()
    thread_a = uuid.uuid4()
    thread_b = uuid.uuid4()
    vector = [0.02] * profile.dimensions
    video = _record(
        workspace_id=workspace_id,
        video_id=video_id,
        thread_id=thread_a,
        origin=ORIGIN_VIDEO,
        text="Leaves capture sunlight and make glucose.",
        vector=vector,
    )
    external = _record(
        workspace_id=workspace_id,
        video_id=video_id,
        thread_id=thread_a,
        origin=ORIGIN_EXTERNAL,
        text="Leaves capture sunlight and make glucose.",
        vector=vector,
        evidence_id=uuid.uuid4(),
    )
    blank = _record(
        workspace_id=workspace_id,
        video_id=video_id,
        thread_id=thread_a,
        origin="",
        text="Leaves capture sunlight and make glucose.",
        vector=vector,
    )
    other_thread = _record(
        workspace_id=workspace_id,
        video_id=video_id,
        thread_id=thread_b,
        origin=ORIGIN_EXTERNAL,
        text="Leaves capture sunlight and make glucose.",
        vector=vector,
        evidence_id=uuid.uuid4(),
    )
    store.upsert_chunks(
        collection=collection,
        profile_id=profile.profile_id,
        dimensions=profile.dimensions,
        records=[video, external, blank, other_thread],
    )
    scope = build_tenant_scope(
        workspace_id=workspace_id,
        video_ids=[video_id],
        evidence_origin=ORIGIN_VIDEO,
        thread_id=thread_a,
    )
    assert payload_matches_scope(video.payload(), scope)
    assert not payload_matches_scope(external.payload(), scope)
    assert not payload_matches_scope(blank.payload(), scope)
    assert not payload_matches_scope(other_thread.payload(), scope)
    result = store.search(
        collection=collection,
        dimensions=profile.dimensions,
        query_text="glucose sunlight",
        dense_vector=vector,
        scope=scope,
        top_k=10,
        dense_only=False,
        prefetch_limit=20,
    )
    assert [hit.chunk_id for hit in result.hits] == [video.chunk_id]
    assert "evidence_origin" in PAYLOAD_INDEX_FIELDS
    assert "thread_id" in PAYLOAD_INDEX_FIELDS


@pytest.mark.asyncio
async def test_lexical_fallback_keeps_the_overlapping_passage() -> None:
    class FailingReranker:
        async def rerank(
            self,
            *,
            question: str,
            passages: list[LanePassage],
        ) -> list[tuple[uuid.UUID, float]]:
            del question, passages
            raise RuntimeError("rerank model unavailable")

    matching = LanePassage(
        id=uuid.uuid4(),
        evidence_origin=ORIGIN_VIDEO,
        evidence_provider="gemini_youtube",
        text="Photosynthesis converts sunlight into glucose in leaves.",
    )
    unrelated = LanePassage(
        id=uuid.uuid4(),
        evidence_origin=ORIGIN_VIDEO,
        evidence_provider="gemini_youtube",
        text="The Roman senate debated grain subsidies.",
    )
    question = "How does photosynthesis make glucose?"
    assert lexical_score(question, unrelated.text) < VIDEO_COVERAGE_THRESHOLD
    _scored, kept = await rank_lane(
        question=question,
        passages=[unrelated, matching],
        origin=ORIGIN_VIDEO,
        reranker=FailingReranker(),
    )
    assert [passage.id for passage in kept] == [matching.id]


@pytest.mark.asyncio
async def test_reindex_reuses_the_same_point(settings: Settings) -> None:
    profile = active_embedding_profile(settings)
    point = OriginPoint(
        workspace_id=uuid.uuid4(),
        video_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        evidence_origin=ORIGIN_VIDEO,
        evidence_provider="gemini_youtube",
        content_hash="hash-1",
        text="Leaves capture sunlight.",
        source_url="https://www.youtube.com/watch?v=abcdefghijk",
        source_asset_id=uuid.uuid4(),
        segment_id=uuid.uuid4(),
    )
    await index_origin_points(settings, [point])
    await index_origin_points(settings, [point])
    store = build_vector_store(settings)
    assert store.count_points(collection_name_for(profile.profile_id)) == 1


def test_unrelated_question_with_search_off_abstains(client: TestClient) -> None:
    _register(client, "rerank-abstain@example.com")
    saved = _save_transcript(client, GLUCOSE_LESSON)
    created = _post(client, saved["video"]["id"], "How do black holes form?", external_search=False)
    body = created["assistant_message"]["content_json"]
    assert body["decision"] == "abstain"
    assert body["external"] == []
    assert body["sources"] == []
    assert body["kept"] == []
    assert body["lesson"] == [
        {"heading": "Coverage", "body": "The video does not cover this question."}
    ]
    assert "score" not in body
    assert _segment_count(client, saved["video"]["id"]) == 3


def test_retrieve_route_keeps_the_video_lane_first(client: TestClient) -> None:
    class ScriptedReranker:
        def __init__(self) -> None:
            self.calls: list[list[tuple[str, str]]] = []

        async def rerank(
            self,
            *,
            question: str,
            passages: list[LanePassage],
        ) -> list[tuple[uuid.UUID, float]]:
            del question
            self.calls.append([(passage.evidence_origin, passage.text) for passage in passages])
            scored: list[tuple[uuid.UUID, float]] = []
            for passage in passages:
                if passage.evidence_origin == ORIGIN_EXTERNAL:
                    score = 0.99
                elif "glucose" in passage.text.lower():
                    score = 0.8
                else:
                    score = 0.0
                scored.append((passage.id, score))
            return scored

    reranker = ScriptedReranker()
    client.app.state.session_reranker = reranker
    _register(client, "rerank-route@example.com")
    saved = _save_transcript(client, GLUCOSE_LESSON)
    video_id = saved["video"]["id"]
    first = _retrieve(
        client,
        video_id,
        "How does photosynthesis make glucose?",
        external_search=True,
        sources=[
            {
                "title": "Quasar survey",
                "url": PAPER_URL,
                "snippet": OUTSIDE,
                "kind": "paper",
                "provider": "semantic_scholar",
            }
        ],
    )
    assert first["decision"] == "blend"
    assert [row["evidence_origin"] for row in first["passages"]] == [
        ORIGIN_VIDEO,
        ORIGIN_EXTERNAL,
    ]
    assert "glucose" in first["passages"][0]["text"].lower()
    assert "senate" not in first["passages"][0]["text"].lower()
    assert OUTSIDE not in first["passages"][0]["text"]
    assert first["passages"][1]["text"] == OUTSIDE
    assert all("score" not in row for row in first["passages"])
    assert reranker.calls[0] and all(origin == ORIGIN_VIDEO for origin, _text in reranker.calls[0])
    assert OUTSIDE not in reranker.calls[0][0][1]
    assert all(origin == ORIGIN_EXTERNAL for origin, _text in reranker.calls[1])
    assert _segment_count(client, video_id) == 3
    assert _evidence_count(client, video_id) == 1
    points_after_first = _point_count(client)
    again = _retrieve(
        client,
        video_id,
        "How does photosynthesis make glucose?",
        external_search=True,
        sources=[
            {
                "title": "Quasar survey",
                "url": PAPER_URL,
                "snippet": OUTSIDE,
                "kind": "paper",
                "provider": "semantic_scholar",
            }
        ],
    )
    assert again["passages"][0]["id"] == first["passages"][0]["id"]
    assert _evidence_count(client, video_id) == 1
    assert _point_count(client) == points_after_first

    reranker.calls.clear()
    off = _retrieve(
        client,
        video_id,
        "How does photosynthesis make glucose?",
        external_search=False,
        sources=[
            {
                "title": "Should not store",
                "url": "https://doi.org/10.1000/ignored",
                "snippet": "IGNORED_EXTERNAL_SNIPPET",
                "kind": "paper",
                "provider": "tavily",
            }
        ],
    )
    assert off["decision"] == "lesson_only"
    assert [row["evidence_origin"] for row in off["passages"]] == [ORIGIN_VIDEO]
    assert OUTSIDE not in str(off)
    assert "IGNORED_EXTERNAL_SNIPPET" not in str(off)
    assert reranker.calls
    assert all(
        origin == ORIGIN_VIDEO
        for call in reranker.calls
        for origin, _text in call
    )
    assert _evidence_count(client, video_id) == 1

    other = _save_transcript(client, "Circuit boards route electrical current through copper.")
    isolated = _retrieve(
        client,
        other["video"]["id"],
        "How do circuit boards route current?",
        external_search=True,
        sources=[],
    )
    assert PAPER_URL not in str(isolated)
    assert OUTSIDE not in str(isolated)
    leaked = [
        text
        for call in reranker.calls
        for _origin, text in call
        if OUTSIDE in text
    ]
    assert leaked == []


def test_trim_deletes_external_rows_and_both_origins(client: TestClient) -> None:
    _register(client, "rerank-trim@example.com")
    limited = client.put(
        "/api/v1/settings/learning-history",
        headers=auth_csrf_headers(client),
        json={"learning_history_limit": 1},
    )
    assert limited.status_code == 200, limited.text
    older = _save_transcript(client, "Older lesson passage about tides.")
    _retrieve(
        client,
        older["video"]["id"],
        "What do tides do?",
        external_search=True,
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
    assert _evidence_count(client, older["video"]["id"]) == 1
    assert older["video"]["id"] in _indexed_video_ids(client)
    _save_transcript(client, "Newer lesson passage about comets.")
    assert _evidence_count(client, older["video"]["id"]) == 0
    assert older["video"]["id"] not in _indexed_video_ids(client)


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Learner"},
    )
    assert response.status_code == 201, response.text


def _save_transcript(client: TestClient, transcript: str) -> dict:
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


def _post(client: TestClient, video_id: str, question: str, *, external_search: bool) -> dict:
    response = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/messages",
        headers=auth_csrf_headers(client),
        json={
            "question": question,
            "explanation_mode": "standard",
            "external_search": external_search,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _retrieve(
    client: TestClient,
    video_id: str,
    question: str,
    *,
    external_search: bool,
    sources: list[dict[str, str]],
) -> dict:
    response = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/retrieve",
        headers=auth_csrf_headers(client),
        json={
            "question": question,
            "external_search": external_search,
            "sources": sources,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _segment_count(client: TestClient, video_id: str) -> int:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> int:
        async with session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(TranscriptSegment)
                .where(TranscriptSegment.video_id == uuid.UUID(video_id))
            )
            return int(result.scalar_one())

    return anyio.run(_run)


def _evidence_count(client: TestClient, video_id: str) -> int:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> int:
        async with session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(ExternalEvidence)
                .where(ExternalEvidence.video_id == uuid.UUID(video_id))
            )
            return int(result.scalar_one())

    return anyio.run(_run)


def _point_count(client: TestClient) -> int:
    settings: Settings = client.app.state.settings
    profile = active_embedding_profile(settings)
    store = build_vector_store(settings)
    return store.count_points(collection_name_for(profile.profile_id))


def _indexed_video_ids(client: TestClient) -> set[str]:
    settings: Settings = client.app.state.settings
    profile = active_embedding_profile(settings)
    store = build_vector_store(settings)
    collection = store._collections.get(collection_name_for(profile.profile_id))  # noqa: SLF001
    if collection is None:
        return set()
    return {str(data["payload"].get("video_id")) for data in collection.points.values()}


def _record(
    *,
    workspace_id: uuid.UUID,
    video_id: uuid.UUID,
    thread_id: uuid.UUID,
    origin: str,
    text: str,
    vector: list[float],
    evidence_id: uuid.UUID | None = None,
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
        evidence_id=evidence_id,
        source_url="https://example.test/source",
    )
