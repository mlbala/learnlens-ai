"""Video metadata import, transcript upload, and workspace-scoped reads."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import CsrfAuth, CurrentAuth, DbSession, SettingsDep
from app.api.v1.schemas import (
    ImportNoticeOut,
    TranscriptUploadAccepted,
    VideoImportResponse,
    VideoListResponse,
    VideoOut,
    YoutubeImportRequest,
)
from app.core.errors import not_found, raise_api_error
from app.services.access import AccessService
from app.services.transcript_ingest import TranscriptIngestError, TranscriptIngestService
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
