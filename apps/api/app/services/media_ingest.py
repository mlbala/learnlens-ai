"""Opt-in authorized media ingest — STT/vision, never YouTube downloads."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.media.factory import get_speech_to_text, get_vision_extract
from app.core.observability.dead_letter import evaluate_retry
from app.core.observability.metrics import get_worker_metrics
from app.core.observability.tracing import celery_headers_from_context, start_span
from app.core.policies.audit_policy import AuditRecord, get_audit_policy
from app.core.policies.privacy_policy import PrivacyPolicy
from app.core.policies.usage_policy import UsageQuotaExceeded, get_usage_policy
from app.core.settings import Settings
from app.db.models import IngestionJob, MediaAsset
from app.db.repositories import IngestionJobRepository, PlaylistRepository, VideoRepository
from app.db.repositories.assets import SourceAssetRepository, TranscriptSegmentRepository
from app.db.repositories.audit import AuditEventRepository
from app.db.repositories.media import MediaAssetRepository, MediaFrameRepository
from app.domain.job_states import JobStage, JobStatus
from app.domain.media_validate import (
    ALIGNMENT_CONFIDENCE_FLOOR,
    MediaValidateError,
    timecode_quality_for_cues,
    validate_media_upload,
)
from app.domain.transcript_parse import ParsedCue, sha256_hex
from app.services.usage import UsageService, WorkspaceQuotaExceeded
from app.storage.factory import get_media_storage_adapter

logger = logging.getLogger(__name__)

JOB_TYPE_MEDIA = "media_ingest"
SOURCE_KIND_LICENSED = "licensed_media"


class MediaIngestError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class MediaIngestResult:
    job: IngestionJob
    media_asset: MediaAsset | None
    created: bool
    replay: bool


class MediaIngestService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._videos = VideoRepository(session)
        self._playlists = PlaylistRepository(session)
        self._jobs = IngestionJobRepository(session)
        self._assets = SourceAssetRepository(session)
        self._segments = TranscriptSegmentRepository(session)
        self._media = MediaAssetRepository(session)
        self._frames = MediaFrameRepository(session)
        self._storage = get_media_storage_adapter(settings)

    async def ingest(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        raw: bytes,
        rights_attested: bool,
        provider_transfer_consented: bool,
        filename: str | None,
        content_type: str | None,
        idempotency_key: str | None,
    ) -> MediaIngestResult:
        if not self._settings.media_processing_enabled:
            raise MediaIngestError(
                403,
                "MEDIA_PROCESSING_DISABLED",
                "Authorized media processing is disabled. An operator must enable "
                "MEDIA_PROCESSING_ENABLED.",
            )
        if not rights_attested:
            raise MediaIngestError(
                403,
                "RIGHTS_ATTESTATION_REQUIRED",
                "You must attest that you own this media or have permission to process it.",
            )
        if not provider_transfer_consented:
            raise MediaIngestError(
                403,
                "PROVIDER_TRANSFER_CONSENT_REQUIRED",
                "Per-provider transfer consent is required before media may be processed.",
            )

        try:
            validated = validate_media_upload(
                raw=raw,
                filename=filename,
                content_type=content_type,
                max_bytes=self._settings.media_max_upload_bytes,
            )
        except MediaValidateError as exc:
            status = 413 if exc.code == "PAYLOAD_TOO_LARGE" else 422
            if exc.code == "MEDIA_QUARANTINED":
                status = 422
            raise MediaIngestError(status, exc.code, exc.message) from exc

        usage = get_usage_policy()
        try:
            usage.check_media_job_allowed(str(user_id))
        except UsageQuotaExceeded as exc:
            raise MediaIngestError(429, exc.code, exc.message) from exc

        workspace_usage = UsageService(self._session, self._settings)
        try:
            await workspace_usage.check_job_allowed(workspace_id)
        except WorkspaceQuotaExceeded as exc:
            raise MediaIngestError(429, exc.code, exc.message) from exc

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
                    metadata={"reason": "cross_tenant_or_missing", "pipeline": "media"},
                )
            )
            raise MediaIngestError(404, "NOT_FOUND", "Resource not found.")

        content_hash = sha256_hex(raw)
        key = idempotency_key or (
            f"media:{workspace_id}:{video_id}:{content_hash}"
        )
        existing = await self._jobs.get_by_idempotency_key(key)
        if existing is not None:
            if existing.workspace_id != workspace_id:
                raise MediaIngestError(404, "NOT_FOUND", "Resource not found.")
            media = None
            if existing.result_resource_id is not None:
                media = await self._media.get_in_workspace(
                    media_asset_id=existing.result_resource_id,
                    workspace_id=workspace_id,
                )
            return MediaIngestResult(
                job=existing, media_asset=media, created=False, replay=True
            )

        stored = self._storage.put_bytes(
            workspace_id=str(workspace_id),
            data=raw,
            content_hash=content_hash,
            content_type=validated.content_type,
        )
        now = datetime.now(UTC)
        media_asset = await self._media.create(
            workspace_id=workspace_id,
            video_id=video.id,
            media_kind=validated.media_kind.value,
            storage_key=stored.storage_key,
            content_hash=content_hash,
            content_type=validated.content_type,
            size_bytes=validated.size_bytes,
            filename=validated.filename,
            rights_attested_at=now,
            provider_transfer_consented_at=now,
            uploaded_by=user_id,
            antivirus_status=validated.antivirus_status,
            status="queued",
        )

        if video.status in {
            "needs_transcript",
            "fixture",
            "imported",
            "unavailable",
            "failed",
            "metadata_only",
        }:
            video.status = "validating"

        job = await self._jobs.create_queued(
            workspace_id=workspace_id,
            video_id=video.id,
            source_asset_id=None,
            job_type=JOB_TYPE_MEDIA,
            idempotency_key=key,
            result_resource_id=media_asset.id,
        )

        usage.record_media_job(str(user_id))
        await workspace_usage.record_job(workspace_id)
        get_worker_metrics().record_enqueue("media")

        audit_meta = {
            "media_kind": validated.media_kind.value,
            "content_hash": content_hash,
            "size_bytes": validated.size_bytes,
            "antivirus_status": validated.antivirus_status,
            "filename_sanitized": validated.filename,
            "provider_transfer_consented": True,
            "pipeline": "media",
        }
        get_audit_policy().record(
            AuditRecord(
                action="media_upload",
                workspace_id=workspace_id,
                actor_user_id=user_id,
                resource_type="video",
                resource_id=str(video.id),
                metadata=audit_meta,
            )
        )
        await AuditEventRepository(self._session).create(
            action="media_upload",
            workspace_id=workspace_id,
            actor_user_id=user_id,
            resource_type="video",
            resource_id=str(video.id),
            metadata=audit_meta,
            summary="Rights-attested media queued",
        )

        logger.info(
            "media_ingest_queued",
            extra={
                "job_id": str(job.id),
                "video_id": str(video.id),
                "workspace_id": str(workspace_id),
                "media_kind": validated.media_kind.value,
                "content_hash": content_hash,
                "size_bytes": validated.size_bytes,
            },
        )

        from app.workers.celery_app import is_eager
        from app.workers.tasks import process_media_job

        if is_eager():
            max_attempts = self._settings.media_job_max_attempts
            for _ in range(max_attempts):
                job = await self.process_job(job.id)
                if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                    break
            media_asset = await self._media.get_in_workspace(
                media_asset_id=media_asset.id,
                workspace_id=workspace_id,
            )
        else:
            await self._session.commit()
            process_media_job.apply_async(
                args=(str(job.id),),
                headers=celery_headers_from_context(),
            )
            await self._session.refresh(job)

        return MediaIngestResult(
            job=job, media_asset=media_asset, created=True, replay=False
        )

    async def process_job(self, job_id: uuid.UUID) -> IngestionJob:
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise MediaIngestError(404, "NOT_FOUND", "Job not found.")
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            return job
        max_attempts = self._settings.media_job_max_attempts
        with start_span(
            "media.process_job",
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
                    stage=JobStage.SCANNING,
                    increment_attempt=True,
                )

            if job.result_resource_id is None:
                raise MediaIngestError(
                    422, "MEDIA_ASSET_MISSING", "Job is missing a media asset."
                )

            media = await self._media.get_in_workspace(
                media_asset_id=job.result_resource_id,
                workspace_id=job.workspace_id,
            )
            if media is None:
                raise MediaIngestError(
                    404, "MEDIA_ASSET_MISSING", "Media asset not found."
                )

            raw = self._storage.get_bytes(media.storage_key)
            # Re-scan on worker (fail closed).
            from app.domain.media_validate import antivirus_scan

            if antivirus_scan(raw) != "clean":
                raise MediaIngestError(
                    422,
                    "MEDIA_QUARANTINED",
                    "Upload failed antivirus/file-type screening and was rejected.",
                )

            await self._jobs.transition(
                job, status=JobStatus.RUNNING, stage=JobStage.TRANSCRIBING
            )
            stt = get_speech_to_text(self._settings)
            speech = await stt.transcribe(
                media_bytes=raw,
                media_kind=media.media_kind,
                content_hash=media.content_hash,
                max_duration_ms=self._settings.media_max_duration_ms,
            )

            await self._jobs.transition(
                job, status=JobStatus.RUNNING, stage=JobStage.EXTRACTING_FRAMES
            )
            vision = get_vision_extract(self._settings)
            vision_result = await vision.extract_frames(
                media_bytes=raw,
                media_kind=media.media_kind,
                content_hash=media.content_hash,
                max_frames=self._settings.media_max_frames,
            )

            cpu_used = speech.estimated_cpu_units + vision_result.estimated_cpu_units
            cost_used = speech.estimated_cost_usd + vision_result.estimated_cost_usd
            if cpu_used > self._settings.media_max_cpu_units_per_job:
                raise MediaIngestError(
                    429,
                    "MEDIA_CPU_CAP_EXCEEDED",
                    "Media processing exceeded the per-job CPU cap.",
                )
            if cost_used > self._settings.media_max_cost_usd_per_job:
                raise MediaIngestError(
                    429,
                    "MEDIA_COST_CAP_EXCEEDED",
                    "Media processing exceeded the per-job cost cap.",
                )

            await self._jobs.transition(
                job, status=JobStatus.RUNNING, stage=JobStage.ALIGNING
            )

            frame_rows: list[dict] = []
            for frame in vision_result.frames:
                frame_key = None
                if frame.frame_bytes:
                    stored_frame = self._storage.put_bytes(
                        workspace_id=str(job.workspace_id),
                        data=frame.frame_bytes,
                        content_hash=sha256_hex(frame.frame_bytes),
                        content_type="application/octet-stream",
                    )
                    frame_key = stored_frame.storage_key
                # Never promote uncertain timing to exact evidence.
                ts = frame.timestamp_ms
                if frame.alignment_confidence < ALIGNMENT_CONFIDENCE_FLOOR:
                    ts = None
                frame_rows.append(
                    {
                        "ordinal": frame.ordinal,
                        "timestamp_ms": ts,
                        "frame_kind": frame.frame_kind,
                        "description": frame.description,
                        "storage_key": frame_key,
                        "alignment_confidence": frame.alignment_confidence,
                        "provenance": frame.provenance,
                    }
                )
            await self._frames.replace_for_asset(
                media_asset_id=media.id,
                workspace_id=job.workspace_id,
                video_id=media.video_id,
                frames=frame_rows,
            )

            cues: list[ParsedCue] = []
            cue_meta: list[tuple[int | None, int | None, float]] = []
            for cue in speech.cues:
                start = cue.start_ms
                end = cue.end_ms
                if cue.alignment_confidence < ALIGNMENT_CONFIDENCE_FLOOR:
                    start = None
                    end = None
                cues.append(
                    ParsedCue(
                        ordinal=cue.ordinal,
                        text=cue.text,
                        start_ms=start,
                        end_ms=end,
                    )
                )
                cue_meta.append((start, end, cue.alignment_confidence))

            quality = timecode_quality_for_cues(cue_meta)
            revision = await self._assets.next_revision(
                video_id=media.video_id,
                workspace_id=job.workspace_id,
            )
            if media.uploaded_by is None:
                raise MediaIngestError(
                    422, "MEDIA_UPLOADER_MISSING", "Media asset is missing uploader."
                )
            source_asset = await self._assets.create(
                video_id=media.video_id,
                workspace_id=job.workspace_id,
                source_kind=SOURCE_KIND_LICENSED,
                storage_key=media.storage_key,
                content_hash=media.content_hash,
                rights_attested_at=media.rights_attested_at or datetime.now(UTC),
                uploaded_by=media.uploaded_by,
                timecode_quality=quality,
                source_revision=revision,
            )
            await self._segments.replace_for_asset(
                asset_id=source_asset.id,
                video_id=media.video_id,
                workspace_id=job.workspace_id,
                cues=cues,
            )
            # Link job to derived source asset for downstream transcript consumers.
            job.source_asset_id = source_asset.id
            await self._session.flush()

            result_json = {
                "stt_provider": speech.provider,
                "stt_model": speech.model,
                "vision_provider": vision_result.provider,
                "vision_model": vision_result.model,
                "cue_count": len(cues),
                "frame_count": len(frame_rows),
                "timecode_quality": quality,
                "alignment_floor": ALIGNMENT_CONFIDENCE_FLOOR,
                "estimated_cpu_units": cpu_used,
                "estimated_cost_usd": cost_used,
                "cue_provenance": [
                    {
                        "ordinal": c.ordinal,
                        "alignment_confidence": c.alignment_confidence,
                        "provenance": c.provenance,
                        "timing_verified": (
                            c.alignment_confidence >= ALIGNMENT_CONFIDENCE_FLOOR
                            and c.start_ms is not None
                        ),
                    }
                    for c in speech.cues
                ],
                "origin": "fixture_data"
                if speech.provider == "fake"
                else "licensed_media",
            }
            # Strip any accidental long text from result metadata.
            result_json = PrivacyPolicy.redact_mapping(result_json)
            await self._media.update_result(
                media,
                status="ready",
                source_asset_id=source_asset.id,
                result_json=result_json,
            )

            video = await self._videos.get_in_workspace(
                video_id=media.video_id,
                workspace_id=job.workspace_id,
            )
            if video is not None:
                video.status = "ready"
                meta = dict(video.metadata_json or {})
                meta["coverage"] = "licensed_media"
                meta["timecode_quality"] = quality
                meta["source_revision"] = revision
                meta["transcript_access"] = True
                meta["media_asset_id"] = str(media.id)
                video.metadata_json = meta
                await self._playlists.mark_items_ready_for_video(video_id=video.id)

            await self._jobs.transition(
                job,
                status=JobStatus.SUCCEEDED,
                stage=JobStage.COMPLETE,
                result_resource_id=media.id,
                clear_error=True,
            )
            return job
        except Exception as exc:  # noqa: BLE001
            return await self._fail_or_retry(job, exc, max_attempts=max_attempts)

    async def _fail_or_retry(
        self,
        job: IngestionJob,
        exc: Exception,
        *,
        max_attempts: int,
    ) -> IngestionJob:
        code = "MEDIA_PROCESSING_FAILED"
        message = "Media processing failed."
        if isinstance(exc, MediaIngestError):
            code = exc.code
            message = exc.message
        # Cap/consent/quarantine failures are terminal; transient worker errors may retry.
        terminal = code in {
            "MEDIA_QUARANTINED",
            "MEDIA_CPU_CAP_EXCEEDED",
            "MEDIA_COST_CAP_EXCEEDED",
            "MEDIA_ASSET_MISSING",
            "MEDIA_UPLOADER_MISSING",
            "RIGHTS_ATTESTATION_REQUIRED",
            "PROVIDER_TRANSFER_CONSENT_REQUIRED",
            "MEDIA_PROCESSING_DISABLED",
        }
        decision = evaluate_retry(
            attempt=job.attempt,
            max_attempts=max_attempts,
            error_code=code,
            retryable=not terminal,
            queue="media",
        )
        logger.warning(
            "media_job_error",
            extra={
                "job_id": str(job.id),
                "error_code": code,
                "attempt": job.attempt,
                "retry": decision.should_retry,
            },
        )
        del message  # never log raw media / speech text
        if decision.should_retry:
            await self._jobs.transition(
                job,
                status=JobStatus.QUEUED,
                stage=JobStage.PENDING,
                last_error_code=code,
            )
            return job

        final_code = decision.error_code
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
        if job.result_resource_id is not None:
            media = await self._media.get_in_workspace(
                media_asset_id=job.result_resource_id,
                workspace_id=job.workspace_id,
            )
            if media is not None:
                await self._media.update_result(media, status="failed")
        return job
