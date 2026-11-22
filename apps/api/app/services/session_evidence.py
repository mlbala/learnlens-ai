"""Index video passages and outside hits, then read one lane or both."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import build_embedding_model, build_text_model
from app.core.settings import Settings
from app.db.models import ExternalEvidence, TranscriptSegment, Video
from app.retrieval.contracts import ChunkIndexRecord
from app.retrieval.factory import build_vector_store
from app.retrieval.filters import build_tenant_scope
from app.retrieval.profile import active_embedding_profile, verify_vector_dimensions
from app.retrieval.session_lanes import (
    ORIGIN_EXTERNAL,
    ORIGIN_VIDEO,
    LanePassage,
    SessionReranker,
    best_score,
    decide,
    evidence_block,
    kept_refs,
    rank_lane,
    source_kind,
    stable_point_id,
    stored_timing,
)
from app.retrieval.thresholds import VIDEO_COVERAGE_THRESHOLD
from app.services.lesson_history import passage_hash

_PROVIDERS = frozenset({"tavily", "semantic_scholar", "openalex"})
_LANE_CANDIDATES = 24


@dataclass(frozen=True, slots=True)
class OriginPoint:
    workspace_id: uuid.UUID
    video_id: uuid.UUID
    thread_id: uuid.UUID
    evidence_origin: str
    evidence_provider: str
    content_hash: str
    text: str
    source_url: str
    source_asset_id: uuid.UUID
    segment_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    title: str = ""


@dataclass(frozen=True, slots=True)
class SearchHitInput:
    title: str
    url: str
    snippet: str
    provider: str


@dataclass(frozen=True, slots=True)
class EvidencePacket:
    decision: str
    video_covered: bool
    passages: tuple[LanePassage, ...]
    kept: tuple[dict[str, str], ...]
    sources: tuple[dict[str, str], ...]
    prompt_block: str

    def public_passages(self) -> list[dict[str, str]]:
        return [
            {
                "id": str(passage.id),
                "evidence_origin": passage.evidence_origin,
                "evidence_provider": passage.evidence_provider,
                "text": passage.text,
                "title": passage.title,
                "source_url": passage.source_url,
            }
            for passage in self.passages
        ]


class SessionEvidenceService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        reranker: SessionReranker | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._reranker = reranker

    async def store_hits(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        thread_id: uuid.UUID,
        hits: list[SearchHitInput],
    ) -> list[ExternalEvidence]:
        """Write Neon rows for URLs the searcher returned. Never writes transcript_segments."""
        stored: list[ExternalEvidence] = []
        for hit in hits:
            provider = hit.provider.strip()
            url = hit.url.strip()
            if provider not in _PROVIDERS or not url.startswith("http"):
                continue
            snippet = hit.snippet.strip()
            title = hit.title.strip()[:500]
            digest = passage_hash(snippet or title or url)
            existing = await self._session.execute(
                select(ExternalEvidence)
                .where(
                    ExternalEvidence.workspace_id == workspace_id,
                    ExternalEvidence.thread_id == thread_id,
                    ExternalEvidence.evidence_origin == ORIGIN_EXTERNAL,
                    ExternalEvidence.content_hash == digest,
                )
                .limit(1)
            )
            row = existing.scalars().first()
            if row is None:
                row = ExternalEvidence(
                    workspace_id=workspace_id,
                    video_id=video_id,
                    thread_id=thread_id,
                    message_id=None,
                    evidence_origin=ORIGIN_EXTERNAL,
                    evidence_provider=provider,
                    title=title or url[:500],
                    source_url=url[:2048],
                    snippet=snippet,
                    content_hash=digest,
                )
                self._session.add(row)
                await self._session.flush()
            stored.append(row)
        return stored

    async def build_packet(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        thread_id: uuid.UUID,
        question: str,
        external_search: bool,
        watch_url: str,
    ) -> EvidencePacket:
        segments = await self._segments(workspace_id, video_id, thread_id)
        external_rows = (
            await self._external_rows(workspace_id, video_id, thread_id)
            if external_search
            else []
        )
        asset_id = segments[0].asset_id if segments else video_id
        await index_origin_points(
            self._settings,
            _video_points(segments, watch_url=watch_url, asset_id=asset_id),
        )
        if external_search:
            await index_origin_points(
                self._settings,
                _external_points(external_rows, asset_id=asset_id),
            )
        video_passages = await self._search_lane(
            workspace_id=workspace_id,
            video_id=video_id,
            thread_id=thread_id,
            question=question,
            origin=ORIGIN_VIDEO,
            segments=segments,
            external_rows=[],
        )
        text_model = None if self._reranker is not None else build_text_model(self._settings)
        video_scored, video_kept = await rank_lane(
            question=question,
            passages=video_passages,
            origin=ORIGIN_VIDEO,
            text_model=text_model,
            reranker=self._reranker,
        )
        video_best = best_score(video_scored)
        external_kept: list[LanePassage] = []
        if external_search:
            external_passages = await self._search_lane(
                workspace_id=workspace_id,
                video_id=video_id,
                thread_id=thread_id,
                question=question,
                origin=ORIGIN_EXTERNAL,
                segments=[],
                external_rows=external_rows,
            )
            _external_scored, external_kept = await rank_lane(
                question=question,
                passages=external_passages,
                origin=ORIGIN_EXTERNAL,
                text_model=text_model,
                reranker=self._reranker,
            )
        decision = decide(
            external_search=external_search,
            best_video_score=video_best,
            external_kept=len(external_kept),
        )
        video_covered = video_best >= VIDEO_COVERAGE_THRESHOLD and bool(video_kept)
        send_video = list(video_kept) if video_covered else []
        send_external = list(external_kept) if decision == "blend" else []
        passages = tuple(send_video + send_external)
        return EvidencePacket(
            decision=decision,
            video_covered=video_covered,
            passages=passages,
            kept=tuple(kept_refs(list(passages))),
            sources=tuple(_sources(send_external)),
            prompt_block=evidence_block(list(passages)),
        )

    async def _search_lane(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        thread_id: uuid.UUID,
        question: str,
        origin: str,
        segments: list[TranscriptSegment],
        external_rows: list[ExternalEvidence],
    ) -> list[LanePassage]:
        """Filter by origin and thread, then score. The other origin is not fetched."""
        profile = active_embedding_profile(self._settings)
        store = build_vector_store(self._settings)
        collection = store.ensure_collection(
            profile_id=profile.profile_id,
            dimensions=profile.dimensions,
        )
        if store.count_points(collection) == 0:
            return []
        dense = verify_vector_dimensions(
            await build_embedding_model(self._settings).embed_query(question),
            profile=profile,
        )
        scope = build_tenant_scope(
            workspace_id=workspace_id,
            video_ids=[video_id],
            evidence_origin=origin,
            thread_id=thread_id,
        )
        result = store.search(
            collection=collection,
            dimensions=profile.dimensions,
            query_text=question,
            dense_vector=dense,
            scope=scope,
            top_k=_LANE_CANDIDATES,
            dense_only=bool(self._settings.qdrant_dense_only),
            prefetch_limit=max(self._settings.qdrant_prefetch_limit, _LANE_CANDIDATES),
        )
        by_segment = {row.id: row for row in segments}
        by_evidence = {row.id: row for row in external_rows}
        passages: list[LanePassage] = []
        seen: set[uuid.UUID] = set()
        for hit in result.hits:
            payload = hit.payload
            if str(payload.get("evidence_origin") or "") != origin:
                continue
            if origin == ORIGIN_VIDEO:
                raw_id = payload.get("segment_id") or _first(payload.get("segment_ids"))
                row = by_segment.get(_uuid_or_none(raw_id))
                if row is None or row.id in seen:
                    continue
                seen.add(row.id)
                passages.append(
                    LanePassage(
                        id=row.id,
                        evidence_origin=ORIGIN_VIDEO,
                        evidence_provider=row.evidence_provider or "gemini_youtube",
                        text=row.text,
                        title="",
                        source_url=str(payload.get("source_url") or ""),
                    )
                )
            else:
                raw_id = payload.get("evidence_id")
                row_e = by_evidence.get(_uuid_or_none(raw_id))
                if row_e is None or row_e.id in seen:
                    continue
                seen.add(row_e.id)
                passages.append(
                    LanePassage(
                        id=row_e.id,
                        evidence_origin=ORIGIN_EXTERNAL,
                        evidence_provider=row_e.evidence_provider,
                        text=row_e.snippet or row_e.title,
                        title=row_e.title,
                        source_url=row_e.source_url,
                    )
                )
        return passages

    async def _segments(
        self,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> list[TranscriptSegment]:
        result = await self._session.execute(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.workspace_id == workspace_id,
                TranscriptSegment.video_id == video_id,
                TranscriptSegment.thread_id == thread_id,
            )
            .order_by(TranscriptSegment.ordinal.asc(), TranscriptSegment.id.asc())
        )
        return list(result.scalars().all())

    async def _external_rows(
        self,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> list[ExternalEvidence]:
        result = await self._session.execute(
            select(ExternalEvidence)
            .where(
                ExternalEvidence.workspace_id == workspace_id,
                ExternalEvidence.video_id == video_id,
                ExternalEvidence.thread_id == thread_id,
                ExternalEvidence.evidence_origin == ORIGIN_EXTERNAL,
            )
            .order_by(ExternalEvidence.created_at.asc())
        )
        return list(result.scalars().all())


async def index_origin_points(settings: Settings, points: list[OriginPoint]) -> str:
    """Embed with the active profile. Reuse a point when the four identity fields match."""
    profile = active_embedding_profile(settings)
    store = build_vector_store(settings)
    collection = store.ensure_collection(
        profile_id=profile.profile_id,
        dimensions=profile.dimensions,
    )
    if not points:
        return collection
    embedder = build_embedding_model(settings)
    vectors = await embedder.embed_documents([point.text for point in points])
    records: list[ChunkIndexRecord] = []
    for point, vector in zip(points, vectors, strict=True):
        start_ms, end_ms = stored_timing(point.start_ms, point.end_ms)
        verified = verify_vector_dimensions(vector, profile=profile)
        records.append(
            ChunkIndexRecord(
                chunk_id=stable_point_id(
                    workspace_id=point.workspace_id,
                    thread_id=point.thread_id,
                    evidence_origin=point.evidence_origin,
                    content_hash=point.content_hash,
                ),
                workspace_id=point.workspace_id,
                video_id=point.video_id,
                source_asset_id=point.source_asset_id,
                source_revision=1,
                segment_ids=(point.segment_id,) if point.segment_id else (),
                text=point.text,
                dense_vector=verified,
                start_ms=start_ms,
                end_ms=end_ms,
                title=point.title,
                content_hash=point.content_hash,
                embedding_profile=profile.profile_id,
                processing_version="session-evidence-v1",
                text_preview=point.text[:240],
                evidence_origin=point.evidence_origin,
                evidence_provider=point.evidence_provider,
                thread_id=point.thread_id,
                evidence_id=point.evidence_id,
                source_url=point.source_url,
            )
        )
    store.upsert_chunks(
        collection=collection,
        profile_id=profile.profile_id,
        dimensions=profile.dimensions,
        records=records,
    )
    return collection


def video_watch_url(video: Video) -> str:
    return (video.source_url or "").strip()


def _video_points(
    segments: list[TranscriptSegment],
    *,
    watch_url: str,
    asset_id: uuid.UUID,
) -> list[OriginPoint]:
    points: list[OriginPoint] = []
    for segment in segments:
        if segment.thread_id is None:
            continue
        points.append(
            OriginPoint(
                workspace_id=segment.workspace_id,
                video_id=segment.video_id,
                thread_id=segment.thread_id,
                evidence_origin=ORIGIN_VIDEO,
                evidence_provider=segment.evidence_provider or "gemini_youtube",
                content_hash=segment.content_hash,
                text=segment.text,
                source_url=watch_url,
                source_asset_id=segment.asset_id or asset_id,
                segment_id=segment.id,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
            )
        )
    return points


def _external_points(rows: list[ExternalEvidence], *, asset_id: uuid.UUID) -> list[OriginPoint]:
    points: list[OriginPoint] = []
    for row in rows:
        text = row.snippet.strip() or row.title.strip()
        if not text:
            continue
        points.append(
            OriginPoint(
                workspace_id=row.workspace_id,
                video_id=row.video_id,
                thread_id=row.thread_id,
                evidence_origin=ORIGIN_EXTERNAL,
                evidence_provider=row.evidence_provider,
                content_hash=row.content_hash,
                text=text,
                source_url=row.source_url,
                source_asset_id=asset_id,
                evidence_id=row.id,
                title=row.title,
            )
        )
    return points


def _sources(passages: list[LanePassage]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for passage in passages:
        if passage.evidence_provider not in _PROVIDERS or not passage.source_url.startswith("http"):
            continue
        title = passage.title.strip() or passage.source_url
        sources.append(
            {
                "provider": passage.evidence_provider,
                "title": title[:500],
                "url": passage.source_url[:2048],
                "kind": source_kind(passage.source_url),
            }
        )
    return sources


def _first(value: object) -> object:
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return None


def _uuid_or_none(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None
