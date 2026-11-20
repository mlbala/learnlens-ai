"""Hierarchical chunk → chapter → video summarization with evidence gating + cache."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ModelRequest, TextModel
from app.ai.factory import build_text_model
from app.core.settings import Settings
from app.db.models import Chapter, SourceAsset, Summary, TranscriptSegment, Video
from app.db.repositories import (
    ChapterRepository,
    ProviderRunRepository,
    SourceAssetRepository,
    SummaryRepository,
    TranscriptSegmentRepository,
    VideoRepository,
)
from app.domain.chapter_boundaries import detect_chapter_boundaries
from app.domain.chunking import SegmentRef, TextChunk, chunk_segments
from app.domain.evidence import EvidenceValidationError, build_packet, validate_summary_payload
from app.domain.summary_prompts import (
    instructions_for,
    prompt_version,
    user_input_for,
    wrap_evidence_items,
)
from app.domain.summary_schemas import SUMMARY_JSON_SCHEMA, SummaryKind

logger = logging.getLogger(__name__)


class SummarizationError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class SummarizeResult:
    asset: SourceAsset
    chapters: list[Chapter]
    summaries: list[Summary]
    cache_hits: int
    provider_calls: int
    blocked: bool


def make_cache_key(
    *,
    content_hash: str,
    prompt_ver: str,
    provider: str,
    model: str,
    summary_kind: str,
    scope_kind: str,
    scope_id: str,
) -> str:
    raw = "|".join(
        [
            content_hash,
            prompt_ver,
            provider,
            model,
            summary_kind,
            scope_kind,
            scope_id,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SummarizationService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        text_model: TextModel | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._videos = VideoRepository(session)
        self._assets = SourceAssetRepository(session)
        self._segments = TranscriptSegmentRepository(session)
        self._chapters = ChapterRepository(session)
        self._summaries = SummaryRepository(session)
        self._runs = ProviderRunRepository(session)
        self._text = text_model

    def _model(self) -> TextModel:
        if self._text is None:
            self._text = build_text_model(self._settings)
        return self._text

    async def summarize_video(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        kinds: list[SummaryKind] | None = None,
    ) -> SummarizeResult:
        video = await self._videos.get_in_workspace(
            video_id=video_id,
            workspace_id=workspace_id,
        )
        if video is None:
            raise SummarizationError(404, "NOT_FOUND", "Resource not found.")

        asset = await self._assets.latest_for_video(
            video_id=video_id,
            workspace_id=workspace_id,
        )
        if asset is None:
            raise SummarizationError(
                422,
                "SOURCE_TRANSCRIPT_REQUIRED",
                "Upload a permitted transcript to summarize this video.",
            )

        segments = await self._segments.list_for_asset(
            asset_id=asset.id,
            workspace_id=workspace_id,
        )
        if not segments:
            raise SummarizationError(
                422,
                "SOURCE_TRANSCRIPT_REQUIRED",
                "Upload a permitted transcript to summarize this video.",
            )

        kinds = kinds or [
            SummaryKind.SHORT,
            SummaryKind.DETAILED,
            SummaryKind.SIMPLE,
            SummaryKind.TECHNICAL,
        ]
        model = self._model()
        refs = [_to_ref(s) for s in segments]
        workspace_ids = {str(s.id) for s in segments}
        chunks = chunk_segments(refs)

        # Chapter boundaries (deterministic) — always refresh for current revision.
        boundaries = detect_chapter_boundaries(refs, chunks)
        chapter_rows = await self._chapters.replace_for_video(
            video_id=video_id,
            workspace_id=workspace_id,
            source_revision=asset.source_revision,
            chapters=[
                {
                    "title": b.title,
                    "start_segment_id": b.start_segment_id,
                    "end_segment_id": b.end_segment_id,
                    "topic_json": {
                        **b.topic_json,
                        "segment_ids": [str(i) for i in b.segment_ids],
                        "chunk_ordinals": list(b.chunk_ordinals),
                    },
                }
                for b in boundaries
            ],
        )

        cache_hits = 0
        provider_calls = 0
        out_summaries: list[Summary] = []
        blocked_any = False

        # --- chunk notes (internal, kind=short) ---
        chunk_notes: list[dict[str, Any]] = []
        for chunk in chunks:
            note, hit, calls, blocked = await self._summarize_scope(
                workspace_id=workspace_id,
                video=video,
                asset=asset,
                scope_kind="chunk",
                scope_id=chunk.chunk_id,
                summary_kind=SummaryKind.SHORT,
                level="chunk",
                evidence_segments=[
                    s for s in segments if s.id in set(chunk.segment_ids)
                ],
                workspace_segment_ids=workspace_ids,
                model=model,
                extra_content={"chunk": _chunk_meta(chunk)},
            )
            cache_hits += hit
            provider_calls += calls
            blocked_any = blocked_any or blocked
            if note is not None:
                out_summaries.append(note)
                chunk_notes.append(
                    {
                        "chunk_id": str(chunk.chunk_id),
                        "summary": note.content_json.get("summary"),
                        "evidence_segment_ids": note.content_json.get(
                            "evidence_segment_ids", []
                        ),
                    }
                )

        # --- chapter summaries ---
        for chapter, boundary in zip(chapter_rows, boundaries, strict=True):
            chapter_segs = [s for s in segments if s.id in set(boundary.segment_ids)]
            row, hit, calls, blocked = await self._summarize_scope(
                workspace_id=workspace_id,
                video=video,
                asset=asset,
                scope_kind="chapter",
                scope_id=chapter.id,
                summary_kind=SummaryKind.DETAILED,
                level="chapter",
                evidence_segments=chapter_segs,
                workspace_segment_ids=workspace_ids,
                model=model,
                extra_content={
                    "chapter_title": chapter.title,
                    "chunk_notes": [
                        n
                        for n in chunk_notes
                        if any(
                            eid in {str(i) for i in boundary.segment_ids}
                            for eid in n.get("evidence_segment_ids", [])
                        )
                    ],
                },
            )
            cache_hits += hit
            provider_calls += calls
            blocked_any = blocked_any or blocked
            if row is not None:
                out_summaries.append(row)

        # --- video-level kinds ---
        for kind in kinds:
            row, hit, calls, blocked = await self._summarize_scope(
                workspace_id=workspace_id,
                video=video,
                asset=asset,
                scope_kind="video",
                scope_id=video.id,
                summary_kind=kind,
                level="video",
                evidence_segments=segments,
                workspace_segment_ids=workspace_ids,
                model=model,
                # Bound context: pass chapter titles + chunk note digests, not raw 10h dump.
                extra_content={
                    "chapters": [
                        {"id": str(c.id), "title": c.title} for c in chapter_rows
                    ],
                    "chunk_count": len(chunks),
                    "chunk_notes": chunk_notes[:40],
                },
                # Cap evidence for video-level call: first segment of each chunk.
                evidence_cap_segments=_representative_segments(segments, chunks),
            )
            cache_hits += hit
            provider_calls += calls
            blocked_any = blocked_any or blocked
            if row is not None:
                out_summaries.append(row)

        meta = dict(video.metadata_json or {})
        meta["summary_status"] = "blocked" if blocked_any else "ready"
        meta["chapter_count"] = len(chapter_rows)
        meta["chunk_count"] = len(chunks)
        meta["processing_version"] = chunks[0].processing_version if chunks else None
        video.metadata_json = meta

        logger.info(
            "video_summarized",
            extra={
                "video_id": str(video_id),
                "workspace_id": str(workspace_id),
                "cache_hits": cache_hits,
                "provider_calls": provider_calls,
                "blocked": blocked_any,
                "chapter_count": len(chapter_rows),
            },
        )
        return SummarizeResult(
            asset=asset,
            chapters=chapter_rows,
            summaries=out_summaries,
            cache_hits=cache_hits,
            provider_calls=provider_calls,
            blocked=blocked_any,
        )

    async def _summarize_scope(
        self,
        *,
        workspace_id: uuid.UUID,
        video: Video,
        asset: SourceAsset,
        scope_kind: str,
        scope_id: uuid.UUID,
        summary_kind: SummaryKind,
        level: str,
        evidence_segments: list[TranscriptSegment],
        workspace_segment_ids: set[str],
        model: TextModel,
        extra_content: dict[str, Any] | None = None,
        evidence_cap_segments: list[TranscriptSegment] | None = None,
    ) -> tuple[Summary | None, int, int, bool]:
        use_segments = evidence_cap_segments or evidence_segments
        evidence_items = [
            {
                "id": str(s.id),
                "segment_id": str(s.id),
                "ordinal": s.ordinal,
                "text": s.text,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
            }
            for s in use_segments
        ]
        prompt_ids = [str(s.id) for s in use_segments]
        cache_key = make_cache_key(
            content_hash=asset.content_hash,
            prompt_ver=prompt_version(),
            provider=model.provider,
            model=model.model,
            summary_kind=summary_kind.value,
            scope_kind=scope_kind,
            scope_id=str(scope_id),
        )

        cached = await self._summaries.get_by_cache_key(
            workspace_id=workspace_id,
            cache_key=cache_key,
        )
        if cached is not None:
            return cached, 1, 0, cached.status == "blocked"

        request_hash = cache_key
        started = time.perf_counter()
        request = ModelRequest(
            purpose="video_summary" if scope_kind == "video" else f"{scope_kind}_summary",
            instructions=instructions_for(summary_kind, scope=scope_kind),
            user_input=(
                user_input_for(kind=summary_kind, title=video.title or "", level=level)
                + "\n"
                + wrap_evidence_items(evidence_items)
            ),
            evidence=evidence_items,
            response_schema=SUMMARY_JSON_SCHEMA,
            max_output_tokens=min(self._settings.ai_max_output_tokens, 1800),
            temperature=0.0,
            timeout_seconds=self._settings.ai_request_timeout_seconds,
            prompt_version=prompt_version(),
        )

        # Bound input characters (fail closed / truncate evidence, never send secrets).
        if len(request.user_input) > self._settings.ai_max_input_characters:
            if len(use_segments) <= 1:
                raise SummarizationError(
                    413,
                    "SUMMARY_INPUT_TOO_LARGE",
                    "Transcript evidence exceeds the configured input character limit.",
                )
            trimmed = use_segments[: max(1, len(use_segments) // 2)]
            return await self._summarize_scope(
                workspace_id=workspace_id,
                video=video,
                asset=asset,
                scope_kind=scope_kind,
                scope_id=scope_id,
                summary_kind=summary_kind,
                level=level,
                evidence_segments=evidence_segments,
                workspace_segment_ids=workspace_segment_ids,
                model=model,
                extra_content=extra_content,
                evidence_cap_segments=trimmed,
            )

        try:
            result = await model.generate_structured(request)
        except Exception as exc:  # noqa: BLE001 — map to safe failure
            logger.warning(
                "summary_provider_failed",
                extra={
                    "scope_kind": scope_kind,
                    "summary_kind": summary_kind.value,
                    "error_type": type(exc).__name__,
                },
            )
            run = await self._runs.create(
                workspace_id=workspace_id,
                provider=model.provider,
                model=model.model,
                operation=f"summary:{scope_kind}:{summary_kind.value}",
                request_hash=request_hash,
                prompt_version=prompt_version(),
                token_in=None,
                token_out=None,
                latency_ms=int((time.perf_counter() - started) * 1000),
                status="failed",
                metadata_json={"error_kind": type(exc).__name__},
            )
            row = await self._summaries.upsert(
                workspace_id=workspace_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                summary_kind=summary_kind.value,
                revision=asset.source_revision,
                content_json={
                    "summary": "Summary unavailable due to provider error.",
                    "key_points": [],
                    "claims": [],
                    "examples": [],
                    "evidence_segment_ids": [],
                    "origin": "error",
                },
                coverage_json={"status": "failed"},
                provider_run_id=run.id,
                cache_key=cache_key,
                status="failed",
            )
            return row, 0, 1, False

        packet = build_packet(
            workspace_id=workspace_id,
            video_id=video.id,
            source_revision=asset.source_revision,
            workspace_segment_ids=workspace_segment_ids,
            prompt_evidence_ids=prompt_ids,
        )
        try:
            validated = validate_summary_payload(result.parsed, packet)
        except EvidenceValidationError:
            validated = validate_summary_payload(
                {
                    "summary": "",
                    "key_points": [],
                    "claims": result.parsed.get("claims") or [],
                    "examples": [],
                    "evidence_segment_ids": [],
                    "origin": "blocked",
                },
                packet,
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        run = await self._runs.create(
            workspace_id=workspace_id,
            provider=result.usage.provider,
            model=result.usage.model,
            operation=f"summary:{scope_kind}:{summary_kind.value}",
            request_hash=request_hash,
            prompt_version=prompt_version(),
            token_in=result.usage.input_tokens,
            token_out=result.usage.output_tokens,
            latency_ms=latency_ms,
            status="succeeded",
            metadata_json={
                "tokens_estimated": result.usage.tokens_estimated,
                "dropped_citation_ids": validated.dropped_citation_ids[:20],
                "blocked_unsupported": validated.blocked_unsupported,
            },
        )

        content: dict[str, Any] = {
            "summary": validated.summary,
            "key_points": validated.key_points,
            "claims": validated.claims,
            "examples": validated.examples,
            "evidence_segment_ids": validated.evidence_segment_ids,
            "origin": validated.origin,
            "prompt_version": prompt_version(),
        }
        if extra_content:
            content["meta"] = extra_content

        status = "blocked" if validated.blocked_unsupported else "ready"
        row = await self._summaries.upsert(
            workspace_id=workspace_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            summary_kind=summary_kind.value,
            revision=asset.source_revision,
            content_json=content,
            coverage_json={
                "source_revision": asset.source_revision,
                "segment_count": len(evidence_segments),
                "evidence_in_prompt": len(prompt_ids),
                "status": status,
            },
            provider_run_id=run.id,
            cache_key=cache_key,
            status=status,
        )
        return row, 0, 1, validated.blocked_unsupported


def _to_ref(segment: TranscriptSegment) -> SegmentRef:
    return SegmentRef(
        id=segment.id,
        ordinal=segment.ordinal,
        text=segment.text,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        speaker=segment.speaker,
        content_hash=segment.content_hash,
    )


def _chunk_meta(chunk: TextChunk) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk.chunk_id),
        "ordinal": chunk.ordinal,
        "segment_ids": [str(i) for i in chunk.segment_ids],
        "start_ms": chunk.start_ms,
        "end_ms": chunk.end_ms,
        "content_hash": chunk.content_hash,
        "processing_version": chunk.processing_version,
        "token_estimate": chunk.token_estimate,
    }


def _representative_segments(
    segments: list[TranscriptSegment],
    chunks: list[TextChunk],
) -> list[TranscriptSegment]:
    """Bound video-level evidence: one segment per chunk (first ID), preserving order."""
    by_id = {s.id: s for s in segments}
    picked: list[TranscriptSegment] = []
    seen: set[uuid.UUID] = set()
    for chunk in chunks:
        if not chunk.segment_ids:
            continue
        sid = chunk.segment_ids[0]
        if sid in seen:
            continue
        seg = by_id.get(sid)
        if seg is not None:
            picked.append(seg)
            seen.add(sid)
    if not picked:
        return segments[:12]
    return picked
