"""Authorized transcript upload / paste ingestion — creates assets + durable jobs."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability.dead_letter import evaluate_retry
from app.core.observability.metrics import get_worker_metrics
from app.core.observability.tracing import celery_headers_from_context, start_span
from app.core.policies.audit_policy import AuditRecord, get_audit_policy
from app.core.policies.input_policy import InputPolicy, InputPolicyViolation
from app.core.policies.privacy_policy import PrivacyPolicy
from app.core.policies.usage_policy import UsageQuotaExceeded, get_usage_policy
from app.core.settings import Settings
from app.db.models import IngestionJob, SourceAsset, Video
from app.db.repositories import IngestionJobRepository, PlaylistRepository, VideoRepository
from app.db.repositories.assets import SourceAssetRepository, TranscriptSegmentRepository
from app.db.repositories.audit import AuditEventRepository
from app.domain.job_states import JobStage, JobStatus
from app.domain.transcript_parse import (
    SourceKind,
    TranscriptParseError,
    parse_transcript,
    sha256_hex,
)
from app.services.usage import UsageService, WorkspaceQuotaExceeded
from app.storage.factory import get_storage_adapter

logger = logging.getLogger(__name__)

JOB_TYPE_TRANSCRIPT = "transcript_ingest"


class TranscriptIngestError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class TranscriptIngestResult:
    job: IngestionJob
    asset: SourceAsset | None
    created: bool
    replay: bool


class TranscriptIngestService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._videos = VideoRepository(session)
        self._playlists = PlaylistRepository(session)
        self._jobs = IngestionJobRepository(session)
        self._assets = SourceAssetRepository(session)
        self._segments = TranscriptSegmentRepository(session)
        self._storage = get_storage_adapter(settings)

    async def ingest(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        raw: bytes,
        rights_attested: bool,
        filename: str | None,
        content_type: str | None,
        source_kind_hint: str | None,
        idempotency_key: str | None,
    ) -> TranscriptIngestResult:
        if not rights_attested:
            raise TranscriptIngestError(
                403,
                "RIGHTS_ATTESTATION_REQUIRED",
                "You must attest that you own this transcript or have permission to process it.",
            )

        max_bytes = self._settings.transcript_max_upload_bytes
        if len(raw) > max_bytes:
            raise TranscriptIngestError(
                413,
                "PAYLOAD_TOO_LARGE",
                f"Transcript exceeds the {max_bytes} byte upload limit.",
            )

        try:
            safe_filename = InputPolicy.sanitize_upload_filename(filename)
        except InputPolicyViolation as exc:
            raise TranscriptIngestError(422, exc.code, exc.message) from exc

        usage = get_usage_policy()
        try:
            usage.check_job_allowed(str(user_id))
        except UsageQuotaExceeded as exc:
            raise TranscriptIngestError(429, exc.code, exc.message) from exc

        workspace_usage = UsageService(self._session, self._settings)
        try:
            await workspace_usage.check_job_allowed(workspace_id)
        except WorkspaceQuotaExceeded as exc:
            raise TranscriptIngestError(429, exc.code, exc.message) from exc

        video = await self._videos.get_in_workspace(
            video_id=video_id,
            workspace_id=workspace_id,
        )
        if video is None:
            get_audit_policy().record(
                AuditRecord(
                    action="authorization_denied",
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    resource_type="video",
                    resource_id=str(video_id),
                    metadata={"reason": "cross_tenant_or_missing"},
                )
            )
            raise TranscriptIngestError(404, "NOT_FOUND", "Resource not found.")

        key = idempotency_key or self._default_idempotency_key(
            workspace_id=workspace_id,
            video_id=video_id,
            content_hash=sha256_hex(raw),
        )
        existing = await self._jobs.get_by_idempotency_key(key)
        if existing is not None:
            if existing.workspace_id != workspace_id:
                raise TranscriptIngestError(404, "NOT_FOUND", "Resource not found.")
            asset = None
            if existing.source_asset_id is not None:
                asset = await self._assets.get_in_workspace(
                    asset_id=existing.source_asset_id,
                    workspace_id=workspace_id,
                )
            return TranscriptIngestResult(
                job=existing, asset=asset, created=False, replay=True
            )

        hint = self._parse_kind_hint(source_kind_hint)
        try:
            # Validate early so we fail before creating durable rows when content is bad.
            parsed = parse_transcript(
                raw,
                filename=safe_filename,
                content_type=content_type,
                source_kind_hint=hint,
                max_characters=self._settings.transcript_max_characters,
            )
        except TranscriptParseError as exc:
            raise TranscriptIngestError(422, exc.code, exc.message) from exc

        # Score injection-like phrases for audit only — content remains untrusted data.
        suspicion = InputPolicy.score_suspicious_content(
            "\n".join(c.text for c in parsed.cues[:50])
        )

        stored = self._storage.put_bytes(
            workspace_id=str(workspace_id),
            data=raw,
            content_hash=parsed.content_hash,
            content_type=content_type or "text/plain; charset=utf-8",
        )

        revision = await self._assets.next_revision(
            video_id=video.id,
            workspace_id=workspace_id,
        )
        asset = await self._assets.create(
            video_id=video.id,
            workspace_id=workspace_id,
            source_kind=parsed.source_kind.value,
            storage_key=stored.storage_key,
            content_hash=parsed.content_hash,
            rights_attested_at=datetime.now(UTC),
            uploaded_by=user_id,
            timecode_quality=parsed.timecode_quality,
            source_revision=revision,
        )

        # Mark video as validating while the durable job runs.
        if video.status in {"needs_transcript", "fixture", "imported", "unavailable", "failed"}:
            video.status = "validating"

        job = await self._jobs.create_queued(
            workspace_id=workspace_id,
            video_id=video.id,
            source_asset_id=asset.id,
            job_type=JOB_TYPE_TRANSCRIPT,
            idempotency_key=key,
        )

        usage.record_job(str(user_id))
        # Workspace ledger: only on newly created jobs (idempotent replay skips this).
        await workspace_usage.record_job(workspace_id)
        get_worker_metrics().record_enqueue("transcript")
        audit_meta = {
            **PrivacyPolicy.transcript_log_safe(
                character_count=parsed.character_count,
                cue_count=len(parsed.cues),
            ),
            "source_kind": parsed.source_kind.value,
            "content_hash": parsed.content_hash,
            "suspicious_score": suspicion.score,
            "filename_sanitized": safe_filename,
        }
        get_audit_policy().record(
            AuditRecord(
                action="transcript_upload",
                workspace_id=workspace_id,
                actor_user_id=user_id,
                resource_type="video",
                resource_id=str(video.id),
                metadata=audit_meta,
            )
        )
        await AuditEventRepository(self._session).create(
            action="transcript_upload",
            workspace_id=workspace_id,
            actor_user_id=user_id,
            resource_type="video",
            resource_id=str(video.id),
            metadata=audit_meta,
            summary="Rights-attested transcript queued",
        )

        logger.info(
            "transcript_ingest_queued",
            extra={
                "job_id": str(job.id),
                "video_id": str(video.id),
                "workspace_id": str(workspace_id),
                "source_kind": parsed.source_kind.value,
                "source_revision": revision,
                "content_hash": parsed.content_hash,
                "cue_count": len(parsed.cues),
                "suspicious_score": suspicion.score,
            },
        )

        from app.workers.celery_app import is_eager
        from app.workers.tasks import process_transcript_job

        if is_eager():
            # Same session/engine (required for SQLite in-memory tests).
            max_attempts = self._settings.transcript_job_max_attempts
            for _ in range(max_attempts):
                job = await self.process_job(job.id)
                if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                    break
        else:
            # Durable path: commit so the worker session can see the job row.
            await self._session.commit()
            process_transcript_job.apply_async(
                args=(str(job.id),),
                headers=celery_headers_from_context(),
            )
            await self._session.refresh(job)

        return TranscriptIngestResult(job=job, asset=asset, created=True, replay=False)

    async def process_job(self, job_id: uuid.UUID) -> IngestionJob:
        """Execute one bounded attempt of a transcript job (called by worker)."""
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise TranscriptIngestError(404, "NOT_FOUND", "Job not found.")
        if job.status == JobStatus.SUCCEEDED:
            return job
        if job.status == JobStatus.FAILED:
            return job

        max_attempts = self._settings.transcript_job_max_attempts
        with start_span(
            "transcript.process_job",
            job_id=str(job_id),
            workspace_id=str(job.workspace_id),
            attempt=job.attempt,
        ):
            return await self._process_job_inner(job, max_attempts=max_attempts)

    async def _process_job_inner(
        self, job: IngestionJob, *, max_attempts: int
    ) -> IngestionJob:
        try:
            if job.status == JobStatus.QUEUED and job.stage == JobStage.PENDING:
                await self._jobs.transition(
                    job,
                    status=JobStatus.RUNNING,
                    stage=JobStage.VALIDATING,
                    increment_attempt=True,
                )

            if job.source_asset_id is None:
                raise TranscriptIngestError(
                    422, "SOURCE_ASSET_MISSING", "Job is missing a source asset."
                )

            asset = await self._assets.get_in_workspace(
                asset_id=job.source_asset_id,
                workspace_id=job.workspace_id,
            )
            if asset is None:
                raise TranscriptIngestError(
                    404, "SOURCE_ASSET_MISSING", "Source asset not found."
                )

            raw = self._storage.get_bytes(asset.storage_key)
            await self._jobs.transition(
                job, status=JobStatus.RUNNING, stage=JobStage.PERSISTING
            )

            try:
                hint = SourceKind(asset.source_kind)
            except ValueError:
                hint = None
            parsed = parse_transcript(
                raw,
                source_kind_hint=hint,
                max_characters=self._settings.transcript_max_characters,
            )

            await self._jobs.transition(
                job, status=JobStatus.RUNNING, stage=JobStage.SEGMENTING
            )
            await self._segments.replace_for_asset(
                asset_id=asset.id,
                video_id=asset.video_id,
                workspace_id=asset.workspace_id,
                cues=parsed.cues,
            )

            video = await self._videos.get_in_workspace(
                video_id=asset.video_id,
                workspace_id=asset.workspace_id,
            )
            if video is not None:
                video.status = "ready"
                meta = dict(video.metadata_json or {})
                meta["coverage"] = "transcript"
                meta["timecode_quality"] = parsed.timecode_quality
                meta["source_revision"] = asset.source_revision
                meta["transcript_access"] = True
                video.metadata_json = meta
                await self._playlists.mark_items_ready_for_video(video_id=video.id)

            await self._jobs.transition(
                job,
                status=JobStatus.SUCCEEDED,
                stage=JobStage.COMPLETE,
                result_resource_id=asset.id,
                clear_error=True,
            )
            # Best-effort hierarchical summaries (phase 06). Failures must not
            # roll back a successful transcript ingest.
            try:
                from app.services.summarization import SummarizationService

                await SummarizationService(self._session, self._settings).summarize_video(
                    workspace_id=asset.workspace_id,
                    video_id=asset.video_id,
                )
            except Exception as summary_exc:  # noqa: BLE001
                logger.warning(
                    "post_transcript_summarize_failed",
                    extra={
                        "job_id": str(job.id),
                        "video_id": str(asset.video_id),
                        "error_type": type(summary_exc).__name__,
                    },
                )
            return job
        except Exception as exc:  # noqa: BLE001 — map + bounded retry
            return await self._handle_failure(job, exc, max_attempts=max_attempts)

    async def _handle_failure(
        self,
        job: IngestionJob,
        exc: Exception,
        *,
        max_attempts: int,
    ) -> IngestionJob:
        if isinstance(exc, TranscriptParseError):
            code = exc.code
            retryable = False
        elif isinstance(exc, TranscriptIngestError):
            code = exc.code
            retryable = False
        elif isinstance(exc, KeyError):
            code = "STORAGE_OBJECT_MISSING"
            retryable = True
        else:
            code = "TRANSCRIPT_JOB_FAILED"
            retryable = True

        logger.warning(
            "transcript_job_failure",
            extra={
                "job_id": str(job.id),
                "attempt": job.attempt,
                "error_code": code,
                "retryable": retryable,
            },
        )

        decision = evaluate_retry(
            attempt=job.attempt,
            max_attempts=max_attempts,
            error_code=code,
            retryable=retryable,
            queue="transcript",
        )
        if decision.should_retry:
            await self._jobs.transition(
                job,
                status=JobStatus.QUEUED,
                stage=JobStage.PENDING,
                last_error_code=code,
            )
            return job

        final_code = decision.error_code
        if job.status != JobStatus.FAILED:
            # May already be mid-flight; force fail if transition allows, else set fields.
            try:
                await self._jobs.transition(
                    job,
                    status=JobStatus.FAILED,
                    stage=JobStage.ERROR,
                    last_error_code=final_code,
                )
            except Exception:  # noqa: BLE001
                job.status = JobStatus.FAILED
                job.stage = JobStage.ERROR
                job.last_error_code = final_code
                job.percent = 100
                await self._session.flush()

        if job.video_id is not None:
            video = await self._session.get(Video, job.video_id)
            if video is not None and video.workspace_id == job.workspace_id:
                if video.status in {"validating", "segmenting", "queued"}:
                    video.status = "failed"
                    await self._session.flush()
        return job

    @staticmethod
    def _default_idempotency_key(
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        content_hash: str,
    ) -> str:
        return f"transcript:{workspace_id}:{video_id}:{content_hash}"

    @staticmethod
    def _parse_kind_hint(value: str | None) -> SourceKind | None:
        if value is None or value.strip() == "":
            return None
        normalized = value.strip().lower()
        try:
            return SourceKind(normalized)
        except ValueError as exc:
            raise TranscriptIngestError(
                422,
                "INVALID_SOURCE_KIND",
                "source_kind must be one of: srt, vtt, txt, paste.",
            ) from exc
