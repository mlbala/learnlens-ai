"""Playlist / course synthesis from ready per-video summaries only."""

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
from app.db.models import IngestionJob, Playlist, PlaylistItem, Summary, Video
from app.db.repositories import (
    IngestionJobRepository,
    PlaylistRepository,
    ProviderRunRepository,
    SourceAssetRepository,
    SummaryRepository,
    TranscriptSegmentRepository,
    VideoRepository,
)
from app.domain.job_states import JobStage, JobStatus
from app.domain.playlist_synthesis_prompts import (
    instructions,
    prompt_version,
    user_input_for,
    wrap_video_summaries,
)
from app.domain.playlist_synthesis_schemas import (
    PLAYLIST_SUMMARY_KIND,
    PLAYLIST_SYNTHESIS_JSON_SCHEMA,
)
from app.domain.playlist_synthesis_validate import validate_playlist_synthesis_payload
from app.domain.summary_schemas import SummaryKind
from app.services.summarization import SummarizationService, make_cache_key

logger = logging.getLogger(__name__)

JOB_TYPE_PLAYLIST_SYNTHESIS = "playlist_synthesis"


class PlaylistSynthesisError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ReadyMember:
    item: PlaylistItem
    video: Video
    source_revision: int
    content_hash: str
    summary: Summary
    evidence_segment_ids: list[str]


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    playlist: Playlist
    summary: Summary
    cache_hit: bool
    video_cache_hits: int
    provider_calls: int
    coverage: dict[str, Any]


def membership_fingerprint(
    *,
    included: list[tuple[uuid.UUID, int]],
    excluded_ids: list[uuid.UUID],
    positions: list[tuple[int, str]],
) -> str:
    """Hash membership + revisions + order so membership/revision changes invalidate."""
    parts = [
        "inc:" + ",".join(f"{vid}:{rev}" for vid, rev in included),
        "exc:" + ",".join(str(x) for x in excluded_ids),
        "ord:" + ",".join(f"{pos}:{yt}" for pos, yt in positions),
        f"pv:{prompt_version()}",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class PlaylistSynthesisService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        text_model: TextModel | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._playlists = PlaylistRepository(session)
        self._videos = VideoRepository(session)
        self._assets = SourceAssetRepository(session)
        self._segments = TranscriptSegmentRepository(session)
        self._summaries = SummaryRepository(session)
        self._runs = ProviderRunRepository(session)
        self._jobs = IngestionJobRepository(session)
        self._text = text_model

    def _model(self) -> TextModel:
        if self._text is None:
            self._text = build_text_model(self._settings)
        return self._text

    async def enqueue(
        self,
        *,
        workspace_id: uuid.UUID,
        playlist_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> tuple[IngestionJob, SynthesisResult | None]:
        playlist = await self._playlists.get_in_workspace(
            playlist_id=playlist_id,
            workspace_id=workspace_id,
        )
        if playlist is None:
            raise PlaylistSynthesisError(404, "NOT_FOUND", "Resource not found.")

        key = idempotency_key or f"playlist-synth:{playlist_id}:{uuid.uuid4()}"
        existing = await self._jobs.get_by_idempotency_key(key)
        if existing is not None and existing.workspace_id == workspace_id:
            if existing.status == JobStatus.SUCCEEDED:
                current = await self.get_summary(
                    workspace_id=workspace_id,
                    playlist_id=playlist_id,
                )
                return existing, current
            if existing.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                return existing, None

        job = await self._jobs.create_queued(
            workspace_id=workspace_id,
            video_id=None,
            source_asset_id=None,
            job_type=JOB_TYPE_PLAYLIST_SYNTHESIS,
            idempotency_key=key,
            result_resource_id=playlist_id,
        )

        from app.workers.celery_app import is_eager

        if is_eager():
            result = await self.process_job(job.id)
            return job, result

        from app.workers.tasks import process_playlist_synthesis_job

        await self._session.commit()
        process_playlist_synthesis_job.delay(str(job.id))
        await self._session.refresh(job)
        return job, None

    async def process_job(self, job_id: uuid.UUID) -> SynthesisResult | None:
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise PlaylistSynthesisError(404, "NOT_FOUND", "Job not found.")
        if job.status == JobStatus.SUCCEEDED:
            if job.result_resource_id is None:
                return None
            return await self.get_summary(
                workspace_id=job.workspace_id,
                playlist_id=job.result_resource_id,
            )
        if job.status == JobStatus.FAILED:
            return None

        playlist_id = job.result_resource_id
        if playlist_id is None:
            await self._jobs.transition(
                job,
                status=JobStatus.FAILED,
                stage=JobStage.ERROR,
                last_error_code="PLAYLIST_MISSING",
            )
            raise PlaylistSynthesisError(422, "PLAYLIST_MISSING", "Job missing playlist id.")

        try:
            if job.status == JobStatus.QUEUED and job.stage == JobStage.PENDING:
                await self._jobs.transition(
                    job,
                    status=JobStatus.RUNNING,
                    stage=JobStage.VALIDATING,
                    increment_attempt=True,
                )
            await self._jobs.transition(
                job, status=JobStatus.RUNNING, stage=JobStage.PERSISTING
            )
            result = await self.synthesize(
                workspace_id=job.workspace_id,
                playlist_id=playlist_id,
            )
            await self._jobs.transition(
                job,
                status=JobStatus.RUNNING,
                stage=JobStage.SEGMENTING,
            )
            await self._jobs.transition(
                job,
                status=JobStatus.SUCCEEDED,
                stage=JobStage.COMPLETE,
                result_resource_id=playlist_id,
                clear_error=True,
            )
            return result
        except PlaylistSynthesisError as exc:
            await self._jobs.transition(
                job,
                status=JobStatus.FAILED,
                stage=JobStage.ERROR,
                last_error_code=exc.code,
            )
            raise
        except Exception as exc:  # noqa: BLE001 — map provider outages to actionable codes
            from app.ai.errors import ProviderError
            from app.core.observability.circuit_breaker import CircuitOpenError
            from app.core.observability.dead_letter import evaluate_retry

            if isinstance(exc, CircuitOpenError):
                code = "PROVIDER_CIRCUIT_OPEN"
                retryable = True
            elif isinstance(exc, ProviderError):
                code = exc.code
                retryable = exc.retryable
            else:
                code = "SYNTHESIS_FAILED"
                retryable = False
            decision = evaluate_retry(
                attempt=job.attempt,
                max_attempts=self._settings.transcript_job_max_attempts,
                error_code=code,
                retryable=retryable,
                queue="playlist_synthesis",
            )
            if decision.should_retry:
                await self._jobs.transition(
                    job,
                    status=JobStatus.QUEUED,
                    stage=JobStage.PENDING,
                    last_error_code=code,
                )
                return None
            await self._jobs.transition(
                job,
                status=JobStatus.FAILED,
                stage=JobStage.ERROR,
                last_error_code=decision.error_code,
            )
            raise

    async def get_summary(
        self,
        *,
        workspace_id: uuid.UUID,
        playlist_id: uuid.UUID,
    ) -> SynthesisResult | None:
        playlist = await self._playlists.get_in_workspace(
            playlist_id=playlist_id,
            workspace_id=workspace_id,
        )
        if playlist is None:
            raise PlaylistSynthesisError(404, "NOT_FOUND", "Resource not found.")

        members, excluded, positions = await self._classify_members(
            workspace_id=workspace_id,
            playlist_id=playlist_id,
            ensure_video_summaries=False,
        )
        fingerprint = membership_fingerprint(
            included=[(m.video.id, m.source_revision) for m in members],
            excluded_ids=[e for e in excluded],
            positions=positions,
        )
        rows = await self._summaries.list_for_scope(
            workspace_id=workspace_id,
            scope_kind="playlist",
            scope_id=playlist_id,
            summary_kind=PLAYLIST_SUMMARY_KIND,
        )
        for row in rows:
            cov = row.coverage_json or {}
            if cov.get("input_fingerprint") == fingerprint and row.status in {
                "ready",
                "blocked",
            }:
                return SynthesisResult(
                    playlist=playlist,
                    summary=row,
                    cache_hit=True,
                    video_cache_hits=0,
                    provider_calls=0,
                    coverage=dict(cov),
                )
        return None

    async def synthesize(
        self,
        *,
        workspace_id: uuid.UUID,
        playlist_id: uuid.UUID,
    ) -> SynthesisResult:
        playlist = await self._playlists.get_in_workspace(
            playlist_id=playlist_id,
            workspace_id=workspace_id,
        )
        if playlist is None:
            raise PlaylistSynthesisError(404, "NOT_FOUND", "Resource not found.")

        members, excluded, positions = await self._classify_members(
            workspace_id=workspace_id,
            playlist_id=playlist_id,
            ensure_video_summaries=True,
        )
        total = len(members) + len(excluded)
        included_ids = [m.video.id for m in members]
        fingerprint = membership_fingerprint(
            included=[(m.video.id, m.source_revision) for m in members],
            excluded_ids=list(excluded),
            positions=positions,
        )
        coverage_label = (
            "complete" if members and len(members) == total else "partial"
        )
        if total == 0:
            coverage_label = "partial"

        model = self._model()
        cache_key = make_cache_key(
            content_hash=fingerprint,
            prompt_ver=prompt_version(),
            provider=model.provider,
            model=model.model,
            summary_kind=PLAYLIST_SUMMARY_KIND,
            scope_kind="playlist",
            scope_id=str(playlist_id),
        )

        cached = await self._summaries.get_by_cache_key(
            workspace_id=workspace_id,
            cache_key=cache_key,
        )
        if cached is not None:
            cov = dict(cached.coverage_json or {})
            return SynthesisResult(
                playlist=playlist,
                summary=cached,
                cache_hit=True,
                video_cache_hits=int(cov.get("video_cache_hits") or 0),
                provider_calls=0,
                coverage=cov,
            )

        video_cache_hits = sum(
            int((m.summary.coverage_json or {}).get("from_cache") or 0) for m in members
        )

        allowed_segments: set[str] = set()
        for m in members:
            allowed_segments.update(m.evidence_segment_ids)

        evidence_packet: list[dict[str, Any]] = []
        for m in members:
            content = m.summary.content_json or {}
            evidence_packet.append(
                {
                    "video_id": str(m.video.id),
                    "title": m.video.title,
                    "summary": content.get("summary") or "",
                    "claims": content.get("claims") or [],
                    "evidence_segment_ids": m.evidence_segment_ids,
                    "id": m.evidence_segment_ids[0] if m.evidence_segment_ids else str(m.video.id),
                    "segment_id": (
                        m.evidence_segment_ids[0]
                        if m.evidence_segment_ids
                        else str(m.video.id)
                    ),
                }
            )

        coverage_base: dict[str, Any] = {
            "coverage_label": coverage_label,
            "coverage_ratio": (len(members) / total) if total else 0.0,
            "included_count": len(members),
            "excluded_count": len(excluded),
            "total_count": total,
            "included_video_ids": [str(v) for v in included_ids],
            "excluded_video_ids": [str(v) for v in excluded],
            "source_revisions": {
                str(m.video.id): m.source_revision for m in members
            },
            "input_fingerprint": fingerprint,
            "caveat": (
                f"Summary covers {len(members)} of {total} videos"
                if total
                else "No playlist items to synthesize"
            ),
        }

        if not members:
            content = {
                "overview": (
                    "No ready lessons with permitted transcripts are available yet. "
                    "Upload authorized transcripts before synthesizing course notes."
                ),
                "topic_modules": [],
                "learning_map": [],
                "cross_video_concepts": [],
                "redundant_topics": [],
                "key_takeaways": [],
                "origin": "fixture_data",
                "prompt_version": prompt_version(),
            }
            row = await self._summaries.upsert(
                workspace_id=workspace_id,
                scope_kind="playlist",
                scope_id=playlist_id,
                summary_kind=PLAYLIST_SUMMARY_KIND,
                revision=1,
                content_json=content,
                coverage_json={**coverage_base, "video_cache_hits": 0, "status": "ready"},
                provider_run_id=None,
                cache_key=cache_key,
                status="ready",
            )
            return SynthesisResult(
                playlist=playlist,
                summary=row,
                cache_hit=False,
                video_cache_hits=0,
                provider_calls=0,
                coverage=dict(row.coverage_json or {}),
            )

        started = time.perf_counter()
        request = ModelRequest(
            purpose="playlist_summary",
            instructions=instructions(),
            user_input=(
                user_input_for(
                    title=playlist.title or "",
                    included_count=len(members),
                    total_count=total,
                )
                + "\n"
                + wrap_video_summaries(evidence_packet)
            ),
            evidence=evidence_packet,
            response_schema=PLAYLIST_SYNTHESIS_JSON_SCHEMA,
            max_output_tokens=min(self._settings.ai_max_output_tokens, 2400),
            temperature=0.0,
            timeout_seconds=self._settings.ai_request_timeout_seconds,
            prompt_version=prompt_version(),
        )

        try:
            result = await model.generate_structured(request)
            provider_calls = 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "playlist_synthesis_provider_failed",
                extra={
                    "playlist_id": str(playlist_id),
                    "error_type": type(exc).__name__,
                },
            )
            run = await self._runs.create(
                workspace_id=workspace_id,
                provider=model.provider,
                model=model.model,
                operation="summary:playlist:course",
                request_hash=cache_key,
                prompt_version=prompt_version(),
                token_in=None,
                token_out=None,
                latency_ms=int((time.perf_counter() - started) * 1000),
                status="failed",
                metadata_json={"error_kind": type(exc).__name__},
            )
            row = await self._summaries.upsert(
                workspace_id=workspace_id,
                scope_kind="playlist",
                scope_id=playlist_id,
                summary_kind=PLAYLIST_SUMMARY_KIND,
                revision=1,
                content_json={
                    "overview": "Course synthesis unavailable due to provider error.",
                    "topic_modules": [],
                    "learning_map": [],
                    "cross_video_concepts": [],
                    "redundant_topics": [],
                    "key_takeaways": [],
                    "origin": "error",
                },
                coverage_json={**coverage_base, "status": "failed"},
                provider_run_id=run.id,
                cache_key=cache_key,
                status="failed",
            )
            return SynthesisResult(
                playlist=playlist,
                summary=row,
                cache_hit=False,
                video_cache_hits=video_cache_hits,
                provider_calls=1,
                coverage=dict(row.coverage_json or {}),
            )

        validated = validate_playlist_synthesis_payload(
            result.parsed,
            included_video_ids={str(v) for v in included_ids},
            allowed_segment_ids=allowed_segments,
        )
        content = {
            "overview": validated.overview,
            "topic_modules": validated.topic_modules,
            "learning_map": validated.learning_map,
            "cross_video_concepts": validated.cross_video_concepts,
            "redundant_topics": validated.redundant_topics,
            "key_takeaways": validated.key_takeaways,
            "origin": validated.origin,
            "prompt_version": prompt_version(),
            # Compatibility fields for generic SummaryOut consumers.
            "summary": validated.overview,
            "key_points": [t["text"] for t in validated.key_takeaways[:20]],
            "claims": [
                {
                    "text": t["text"],
                    "evidence_segment_ids": t["evidence_segment_ids"],
                    "provenance": t["provenance"],
                }
                for t in validated.key_takeaways
                if t.get("provenance") == "source_supported"
            ],
            "examples": [],
            "evidence_segment_ids": sorted(
                {
                    sid
                    for t in validated.key_takeaways
                    for sid in t.get("evidence_segment_ids") or []
                }
            ),
        }

        run = await self._runs.create(
            workspace_id=workspace_id,
            provider=result.usage.provider,
            model=result.usage.model,
            operation="summary:playlist:course",
            request_hash=cache_key,
            prompt_version=prompt_version(),
            token_in=result.usage.input_tokens,
            token_out=result.usage.output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
            status="succeeded",
            metadata_json={
                "tokens_estimated": result.usage.tokens_estimated,
                "dropped_video_ids": validated.dropped_video_ids[:20],
                "dropped_segment_ids": validated.dropped_segment_ids[:20],
                "coverage_label": coverage_label,
            },
        )

        # revision tracks synthesis generation for this fingerprint (stable at 1 per key).
        row = await self._summaries.upsert(
            workspace_id=workspace_id,
            scope_kind="playlist",
            scope_id=playlist_id,
            summary_kind=PLAYLIST_SUMMARY_KIND,
            revision=1,
            content_json=content,
            coverage_json={
                **coverage_base,
                "video_cache_hits": video_cache_hits,
                "status": "ready",
            },
            provider_run_id=run.id,
            cache_key=cache_key,
            status="ready",
        )

        logger.info(
            "playlist_synthesized",
            extra={
                "playlist_id": str(playlist_id),
                "workspace_id": str(workspace_id),
                "included": len(members),
                "excluded": len(excluded),
                "coverage_label": coverage_label,
                "provider_calls": provider_calls,
            },
        )
        return SynthesisResult(
            playlist=playlist,
            summary=row,
            cache_hit=False,
            video_cache_hits=video_cache_hits,
            provider_calls=provider_calls,
            coverage=dict(row.coverage_json or {}),
        )

    async def _classify_members(
        self,
        *,
        workspace_id: uuid.UUID,
        playlist_id: uuid.UUID,
        ensure_video_summaries: bool,
    ) -> tuple[list[ReadyMember], list[uuid.UUID], list[tuple[int, str]]]:
        items = await self._playlists.list_items(playlist_id=playlist_id)
        positions = [(i.playlist_position, i.youtube_video_id) for i in items]
        ready: list[ReadyMember] = []
        summarizer = SummarizationService(
            self._session, self._settings, text_model=self._text
        )

        for item in items:
            if item.video_id is None:
                continue
            video = await self._videos.get_in_workspace(
                video_id=item.video_id,
                workspace_id=workspace_id,
            )
            if video is None:
                continue

            asset = await self._assets.latest_for_video(
                video_id=video.id,
                workspace_id=workspace_id,
            )
            # Sync playlist item readiness when the linked video already has a transcript.
            if video.status == "ready" and asset is not None and item.state != "ready":
                item.state = "ready"
                await self._session.flush()

            if video.status != "ready" or asset is None or item.state != "ready":
                continue

            segments = await self._segments.list_for_asset(
                asset_id=asset.id,
                workspace_id=workspace_id,
            )
            if not segments:
                continue

            summary_row: Summary | None = None
            from_cache = 0
            if ensure_video_summaries:
                result = await summarizer.summarize_video(
                    workspace_id=workspace_id,
                    video_id=video.id,
                    kinds=[SummaryKind.SHORT],
                )
                from_cache = 1 if result.cache_hits > 0 else 0
                for row in result.summaries:
                    if (
                        row.scope_kind == "video"
                        and row.summary_kind == SummaryKind.SHORT.value
                    ):
                        summary_row = row
                        break
                if summary_row is None and result.summaries:
                    summary_row = next(
                        (r for r in result.summaries if r.scope_kind == "video"),
                        result.summaries[-1],
                    )
            else:
                rows = await self._summaries.list_for_scope(
                    workspace_id=workspace_id,
                    scope_kind="video",
                    scope_id=video.id,
                    summary_kind=SummaryKind.SHORT.value,
                )
                summary_row = rows[0] if rows else None

            if summary_row is None or summary_row.status not in {"ready", "blocked"}:
                continue

            evidence_ids = [
                str(s)
                for s in (summary_row.content_json or {}).get("evidence_segment_ids") or []
            ]
            if not evidence_ids:
                evidence_ids = [str(s.id) for s in segments[:3]]

            cov = dict(summary_row.coverage_json or {})
            cov["from_cache"] = from_cache
            summary_row.coverage_json = cov

            ready.append(
                ReadyMember(
                    item=item,
                    video=video,
                    source_revision=asset.source_revision,
                    content_hash=asset.content_hash,
                    summary=summary_row,
                    evidence_segment_ids=evidence_ids,
                )
            )

        ready_ids = {m.video.id for m in ready}
        excluded = []
        for item in items:
            if item.video_id is None:
                excluded.append(item.id)
            elif item.video_id not in ready_ids:
                excluded.append(item.video_id)

        return ready, excluded, positions
