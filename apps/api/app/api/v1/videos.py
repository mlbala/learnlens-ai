"""Video metadata import, transcript upload, and workspace-scoped reads."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import CsrfAuth, CurrentAuth, DbSession, SettingsDep
from app.api.v1.schemas import (
    ChapterListResponse,
    ChapterOut,
    ImportNoticeOut,
    MediaUploadAccepted,
    SummarizeAccepted,
    SummaryClaimOut,
    SummaryExampleOut,
    SummaryListResponse,
    SummaryOut,
    TranscriptUploadAccepted,
    VideoDeleteResponse,
    VideoImportResponse,
    VideoListResponse,
    VideoOut,
    YoutubeImportRequest,
)
from app.core.errors import not_found, raise_api_error
from app.db.repositories import ChapterRepository, SummaryRepository
from app.domain.summary_schemas import SummaryKind
from app.services.access import AccessService
from app.services.media_ingest import MediaIngestError, MediaIngestService
from app.services.summarization import SummarizationError, SummarizationService
from app.services.transcript_ingest import TranscriptIngestError, TranscriptIngestService
from app.services.video_deletion import VideoDeletionError, VideoDeletionService
from app.services.youtube_import import YoutubeImportService, map_youtube_error_to_http
from app.youtube.errors import YoutubeMetadataError

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


def _video_out(video: Any) -> VideoOut:
    meta = video.metadata_json if isinstance(video.metadata_json, dict) else {}
    coverage = meta.get("coverage") if isinstance(meta, dict) else None
    transcript_access = bool(meta.get("transcript_access")) if isinstance(meta, dict) else False
    if video.status == "ready":
        transcript_access = True
    return VideoOut(
        id=video.id,
        workspace_id=video.workspace_id,
        youtube_video_id=video.youtube_video_id,
        title=video.title,
        status=video.status,
        channel_title=video.channel_title,
        duration_seconds=video.duration_seconds,
        source_url=video.source_url,
        metadata_json=video.metadata_json,
        transcript_access=transcript_access,
        coverage=coverage if isinstance(coverage, str) else None,
        pinned=bool(video.pinned),
    )


@router.post("/import", response_model=VideoImportResponse)
async def import_video(
    body: YoutubeImportRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> VideoImportResponse:
    """Import official YouTube metadata for a video URL (no transcript access)."""
    request_id = getattr(request.state, "request_id", None)
    idem = request.headers.get("Idempotency-Key")
    service = YoutubeImportService(db, settings)
    try:
        result = await service.import_video_url(
            workspace_id=ctx.workspace.id,
            youtube_url=body.youtube_url,
            idempotency_key=idem,
        )
    except Exception as exc:  # noqa: BLE001 — mapped below
        if isinstance(exc, YoutubeMetadataError | ValueError):
            status, code, message = map_youtube_error_to_http(exc)
            raise_api_error(status, code=code, message=message, request_id=request_id)
        status, code, message = map_youtube_error_to_http(exc)
        raise_api_error(status, code=code, message=message, request_id=request_id)

    return VideoImportResponse(
        video=_video_out(result.video),
        created=result.created,
        notices=[ImportNoticeOut(code=n.code, message=n.message) for n in result.notices],
        companion_playlist_id=result.companion_playlist_id,
        transcript_from_url=False,
    )


@router.get("", response_model=VideoListResponse)
async def list_videos(
    ctx: CurrentAuth,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    status: str | None = Query(default=None, max_length=32),
) -> VideoListResponse:
    access = AccessService(db)
    videos = await access.list_videos_for_caller(ctx, limit=limit, status=status)
    return VideoListResponse(items=[_video_out(v) for v in videos], limit=limit)


@router.get("/{video_id}", response_model=VideoOut)
async def get_video(
    video_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
) -> VideoOut:
    """Return a video only if it belongs to the authenticated workspace."""
    access = AccessService(db)
    # Ignore any client-supplied workspace_id query/body — scope from session only.
    video = await access.get_video_for_caller(ctx, video_id)
    if video is None:
        from app.core.policies.audit_policy import AuditRecord, get_audit_policy

        get_audit_policy().record(
            AuditRecord(
                action="authorization_denied",
                workspace_id=ctx.workspace.id,
                actor_user_id=ctx.user.id,
                resource_type="video",
                resource_id=str(video_id),
                request_id=getattr(request.state, "request_id", None),
                metadata={"reason": "cross_tenant_or_missing"},
            )
        )
        # Fail closed: do not disclose whether the ID exists in another tenant.
        not_found(getattr(request.state, "request_id", None))
    return _video_out(video)


@router.post(
    "/{video_id}/transcripts",
    response_model=TranscriptUploadAccepted,
    status_code=202,
)
async def upload_transcript(
    video_id: uuid.UUID,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
    rights_attested: Annotated[bool, Form()] = False,
    source_kind: Annotated[str | None, Form()] = None,
    paste_text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> JSONResponse:
    """
    Ingest a rights-attested SRT/VTT/TXT upload or pasted transcript.

    No media download / ASR. Returns 202 with a durable job id.
    """
    request_id = getattr(request.state, "request_id", None)
    idem = request.headers.get("Idempotency-Key")

    raw: bytes
    filename: str | None
    content_type: str | None
    kind_hint = source_kind

    if file is not None and file.filename:
        # Read with hard cap (+1) so oversized payloads fail closed as 413.
        max_bytes = settings.transcript_max_upload_bytes
        raw = await file.read(max_bytes + 1)
        filename = file.filename
        content_type = file.content_type
    elif paste_text is not None and paste_text.strip():
        raw = paste_text.encode("utf-8")
        filename = None
        content_type = "text/plain; charset=utf-8"
        kind_hint = kind_hint or "paste"
    else:
        raise_api_error(
            422,
            code="TRANSCRIPT_REQUIRED",
            message="Provide a transcript file or paste_text.",
            request_id=request_id,
        )

    service = TranscriptIngestService(db, settings)
    try:
        result = await service.ingest(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            video_id=video_id,
            raw=raw,
            rights_attested=rights_attested,
            filename=filename,
            content_type=content_type,
            source_kind_hint=kind_hint,
            idempotency_key=idem,
        )
    except TranscriptIngestError as exc:
        raise_api_error(
            exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    body = TranscriptUploadAccepted(
        job_id=result.job.id,
        status=result.job.status,
        stage=result.job.stage,
        percent=result.job.percent,
        source_asset_id=result.asset.id if result.asset else result.job.source_asset_id,
        source_revision=result.asset.source_revision if result.asset else None,
        timecode_quality=result.asset.timecode_quality if result.asset else None,
        replay=result.replay,
    )
    return JSONResponse(status_code=202, content=body.model_dump(mode="json"))


@router.post(
    "/{video_id}/media",
    response_model=MediaUploadAccepted,
    status_code=202,
)
async def upload_media(
    video_id: uuid.UUID,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
    rights_attested: Annotated[bool, Form()] = False,
    provider_transfer_consented: Annotated[bool, Form()] = False,
    file: Annotated[UploadFile | None, File()] = None,
) -> JSONResponse:
    """
    Opt-in upload of user-owned/licensed audio or video.

    Separate from YouTube URL metadata. Requires rights attestation and
    per-provider transfer consent. No YouTube downloading.
    """
    request_id = getattr(request.state, "request_id", None)
    idem = request.headers.get("Idempotency-Key")

    if file is None or not file.filename:
        raise_api_error(
            422,
            code="MEDIA_REQUIRED",
            message="Provide an authorized media file upload.",
            request_id=request_id,
        )

    max_bytes = settings.media_max_upload_bytes
    raw = await file.read(max_bytes + 1)

    service = MediaIngestService(db, settings)
    try:
        result = await service.ingest(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            video_id=video_id,
            raw=raw,
            rights_attested=rights_attested,
            provider_transfer_consented=provider_transfer_consented,
            filename=file.filename,
            content_type=file.content_type,
            idempotency_key=idem,
        )
    except MediaIngestError as exc:
        raise_api_error(
            exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    media = result.media_asset
    quality = None
    source_asset_id = None
    if media is not None:
        source_asset_id = media.source_asset_id
        if isinstance(media.result_json, dict):
            quality = media.result_json.get("timecode_quality")

    body = MediaUploadAccepted(
        job_id=result.job.id,
        status=result.job.status,
        stage=result.job.stage,
        percent=result.job.percent,
        media_asset_id=media.id if media else result.job.result_resource_id,
        source_asset_id=source_asset_id or result.job.source_asset_id,
        timecode_quality=str(quality) if quality else None,
        media_kind=media.media_kind if media else None,
        replay=result.replay,
    )
    return JSONResponse(status_code=202, content=body.model_dump(mode="json"))


@router.delete("/{video_id}", response_model=VideoDeleteResponse)
async def delete_video(
    video_id: uuid.UUID,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> VideoDeleteResponse:
    """Delete owned video plus media blobs, frames, transcripts, and indexes."""
    request_id = getattr(request.state, "request_id", None)
    service = VideoDeletionService(db, settings)
    try:
        result = await service.delete_video(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            video_id=video_id,
        )
    except VideoDeletionError as exc:
        raise_api_error(
            exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )
    return VideoDeleteResponse(
        video_id=result.video_id,
        media_removed=result.media_removed,
        frames_removed=result.frames_removed,
        storage_keys_removed=result.storage_keys_removed,
        index_points_removed=result.index_points_removed,
    )


@router.get("/{video_id}/chapters", response_model=ChapterListResponse)
async def list_chapters(
    video_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
) -> ChapterListResponse:
    """Return chapter refs for an owned video (empty list if not yet summarized)."""
    access = AccessService(db)
    video = await access.get_video_for_caller(ctx, video_id)
    if video is None:
        not_found(getattr(request.state, "request_id", None))
    chapters = await ChapterRepository(db).list_for_video(
        video_id=video_id,
        workspace_id=ctx.workspace.id,
    )
    revision = chapters[0].source_revision if chapters else None
    return ChapterListResponse(
        items=[
            ChapterOut(
                id=c.id,
                video_id=c.video_id,
                workspace_id=c.workspace_id,
                source_revision=c.source_revision,
                title=c.title,
                start_segment_id=c.start_segment_id,
                end_segment_id=c.end_segment_id,
                topic_json=c.topic_json,
            )
            for c in chapters
        ],
        source_revision=revision,
    )


@router.get("/{video_id}/summaries", response_model=SummaryListResponse)
async def list_summaries(
    video_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    kind: str | None = Query(default=None, max_length=32),
    ensure: bool = Query(default=True),
) -> SummaryListResponse:
    """
    Return video-scope summaries with evidence IDs.

    Without a transcript, returns 422 SOURCE_TRANSCRIPT_REQUIRED (blocked state).
    By default, generates missing summaries via the configured (fake-by-default) provider.
    """
    request_id = getattr(request.state, "request_id", None)
    access = AccessService(db)
    video = await access.get_video_for_caller(ctx, video_id)
    if video is None:
        not_found(request_id)

    summary_kind: SummaryKind | None = None
    if kind:
        try:
            summary_kind = SummaryKind(kind.strip().lower())
        except ValueError:
            raise_api_error(
                422,
                code="INVALID_SUMMARY_KIND",
                message="kind must be one of: short, detailed, simple, technical.",
                request_id=request_id,
            )

    repo = SummaryRepository(db)
    items = await repo.list_for_scope(
        workspace_id=ctx.workspace.id,
        scope_kind="video",
        scope_id=video_id,
        summary_kind=summary_kind.value if summary_kind else None,
    )

    # Prefer latest revision per kind.
    latest: dict[str, Any] = {}
    for row in items:
        if row.summary_kind not in latest:
            latest[row.summary_kind] = row
    items = list(latest.values())

    if ensure and (not items or (summary_kind and summary_kind.value not in latest)):
        service = SummarizationService(db, settings)
        try:
            kinds = [summary_kind] if summary_kind else None
            await service.summarize_video(
                workspace_id=ctx.workspace.id,
                video_id=video_id,
                kinds=kinds,
            )
        except SummarizationError as exc:
            raise_api_error(
                exc.status_code,
                code=exc.code,
                message=exc.message,
                request_id=request_id,
            )
        items = await repo.list_for_scope(
            workspace_id=ctx.workspace.id,
            scope_kind="video",
            scope_id=video_id,
            summary_kind=summary_kind.value if summary_kind else None,
        )
        latest = {}
        for row in items:
            if row.summary_kind not in latest:
                latest[row.summary_kind] = row
        items = list(latest.values())

    blocked = any(row.status == "blocked" for row in items)
    revision = None
    for row in items:
        cov = row.coverage_json or {}
        if isinstance(cov, dict) and cov.get("source_revision") is not None:
            revision = int(cov["source_revision"])
            break

    return SummaryListResponse(
        items=[_summary_out(row) for row in items],
        blocked=blocked,
        source_revision=revision,
    )


@router.post("/{video_id}/summarize", response_model=SummarizeAccepted)
async def summarize_video(
    video_id: uuid.UUID,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> SummarizeAccepted:
    """Run hierarchical summarization for an owned video (fake providers by default)."""
    request_id = getattr(request.state, "request_id", None)
    access = AccessService(db)
    video = await access.get_video_for_caller(ctx, video_id)
    if video is None:
        not_found(request_id)

    service = SummarizationService(db, settings)
    try:
        result = await service.summarize_video(
            workspace_id=ctx.workspace.id,
            video_id=video_id,
        )
    except SummarizationError as exc:
        raise_api_error(
            exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    return SummarizeAccepted(
        video_id=video_id,
        chapter_count=len(result.chapters),
        summary_count=len(result.summaries),
        cache_hits=result.cache_hits,
        provider_calls=result.provider_calls,
        blocked=result.blocked,
        source_revision=result.asset.source_revision,
    )


def _summary_out(row: Any) -> SummaryOut:
    content = row.content_json if isinstance(row.content_json, dict) else {}
    claims_raw = content.get("claims") or []
    examples_raw = content.get("examples") or []
    return SummaryOut(
        id=row.id,
        workspace_id=row.workspace_id,
        scope_kind=row.scope_kind,
        scope_id=row.scope_id,
        summary_kind=row.summary_kind,
        revision=row.revision,
        status=row.status,
        summary=str(content.get("summary") or ""),
        key_points=[str(p) for p in (content.get("key_points") or [])],
        claims=[
            SummaryClaimOut(
                text=str(c.get("text") or ""),
                evidence_segment_ids=[str(i) for i in (c.get("evidence_segment_ids") or [])],
                provenance=str(c.get("provenance") or "source_supported"),
            )
            for c in claims_raw
            if isinstance(c, dict)
        ],
        examples=[
            SummaryExampleOut(
                text=str(e.get("text") or ""),
                origin=str(e.get("origin") or "ai_generated_illustration"),
            )
            for e in examples_raw
            if isinstance(e, dict)
        ],
        evidence_segment_ids=[str(i) for i in (content.get("evidence_segment_ids") or [])],
        origin=str(content.get("origin")) if content.get("origin") is not None else None,
        coverage_json=row.coverage_json,
        provider_run_id=row.provider_run_id,
        cache_hit=False,
    )
