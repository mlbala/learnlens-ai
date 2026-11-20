"""Playlist metadata import, synthesis, and workspace-scoped reads."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.deps import CsrfAuth, CurrentAuth, DbSession, SettingsDep
from app.api.v1.schemas import (
    CrossVideoConceptOut,
    ImportNoticeOut,
    LearningMapNodeOut,
    PlaylistCourseSummaryOut,
    PlaylistImportResponse,
    PlaylistItemOut,
    PlaylistListItemOut,
    PlaylistListResponse,
    PlaylistOut,
    PlaylistSynthesizeAccepted,
    PlaylistTakeawayOut,
    RedundantTopicOut,
    TopicModuleOut,
    YoutubeImportRequest,
)
from app.core.errors import not_found, raise_api_error
from app.db.models import Playlist, PlaylistItem, Summary
from app.services.access import AccessService
from app.services.playlist_synthesis import PlaylistSynthesisError, PlaylistSynthesisService
from app.services.youtube_import import YoutubeImportService, map_youtube_error_to_http
from app.youtube.errors import YoutubeMetadataError

router = APIRouter(prefix="/api/v1/playlists", tags=["playlists"])


def _coverage(items: list[PlaylistItem]) -> dict[str, int]:
    counts = Counter(i.state for i in items)
    return {
        "total": len(items),
        "needs_transcript": counts.get("needs_transcript", 0),
        "unavailable": counts.get("unavailable", 0),
        "ready": counts.get("ready", 0),
        "failed": counts.get("failed", 0),
    }


def _playlist_out(playlist: Playlist, items: list[PlaylistItem]) -> PlaylistOut:
    return PlaylistOut(
        id=playlist.id,
        workspace_id=playlist.workspace_id,
        youtube_playlist_id=playlist.youtube_playlist_id,
        title=playlist.title,
        status=playlist.status,
        total_items=playlist.total_items,
        items=[
            PlaylistItemOut(
                id=item.id,
                playlist_position=item.playlist_position,
                youtube_video_id=item.youtube_video_id,
                video_id=item.video_id,
                state=item.state,
            )
            for item in items
        ],
        coverage=_coverage(items),
        transcript_from_url=False,
    )


@router.get("", response_model=PlaylistListResponse)
async def list_playlists(
    ctx: CurrentAuth,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
) -> PlaylistListResponse:
    """List playlists owned by the authenticated workspace (library screens)."""
    access = AccessService(db)
    playlists = await access.list_playlists_for_caller(ctx, limit=limit)
    items: list[PlaylistListItemOut] = []
    for playlist in playlists:
        playlist_items = await access.list_playlist_items(playlist.id)
        items.append(
            PlaylistListItemOut(
                id=playlist.id,
                workspace_id=playlist.workspace_id,
                youtube_playlist_id=playlist.youtube_playlist_id,
                title=playlist.title,
                status=playlist.status,
                total_items=playlist.total_items,
                coverage=_coverage(playlist_items),
                transcript_from_url=False,
            )
        )
    return PlaylistListResponse(items=items, limit=limit)


@router.post("/import", response_model=PlaylistImportResponse)
async def import_playlist(
    body: YoutubeImportRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> PlaylistImportResponse:
    """Import official YouTube playlist metadata with ordered items (no transcripts)."""
    request_id = getattr(request.state, "request_id", None)
    idem = request.headers.get("Idempotency-Key")
    service = YoutubeImportService(db, settings)
    try:
        result = await service.import_playlist_url(
            workspace_id=ctx.workspace.id,
            youtube_url=body.youtube_url,
            idempotency_key=idem,
        )
    except Exception as exc:  # noqa: BLE001 — mapped below
        status, code, message = map_youtube_error_to_http(exc)
        if not isinstance(exc, YoutubeMetadataError | ValueError) and status == 500:
            raise_api_error(status, code=code, message=message, request_id=request_id)
        raise_api_error(status, code=code, message=message, request_id=request_id)

    return PlaylistImportResponse(
        playlist=_playlist_out(result.playlist, result.items),
        created=result.created,
        truncated=result.truncated,
        notices=[ImportNoticeOut(code=n.code, message=n.message) for n in result.notices],
        transcript_from_url=False,
    )


@router.get("/{playlist_id}", response_model=PlaylistOut)
async def get_playlist(
    playlist_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
) -> PlaylistOut:
    access = AccessService(db)
    playlist = await access.get_playlist_for_caller(ctx, playlist_id)
    if playlist is None:
        not_found(getattr(request.state, "request_id", None))
    items = await access.list_playlist_items(playlist.id)  # type: ignore[union-attr]
    return _playlist_out(playlist, items)  # type: ignore[arg-type]


@router.post(
    "/{playlist_id}/synthesize",
    response_model=PlaylistSynthesizeAccepted,
    status_code=202,
)
async def synthesize_playlist(
    playlist_id: uuid.UUID,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> PlaylistSynthesizeAccepted:
    """Enqueue course-level synthesis over ready per-video summaries only."""
    request_id = getattr(request.state, "request_id", None)
    access = AccessService(db)
    playlist = await access.get_playlist_for_caller(ctx, playlist_id)
    if playlist is None:
        not_found(request_id)

    idem = request.headers.get("Idempotency-Key")
    service = PlaylistSynthesisService(db, settings)
    try:
        job, _result = await service.enqueue(
            workspace_id=ctx.workspace.id,
            playlist_id=playlist_id,
            idempotency_key=idem,
        )
    except PlaylistSynthesisError as exc:
        raise_api_error(
            exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    return PlaylistSynthesizeAccepted(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        percent=job.percent,
        playlist_id=playlist_id,
        replay=bool(idem and job.idempotency_key == idem and job.status == "succeeded"),
    )


@router.get("/{playlist_id}/summary", response_model=PlaylistCourseSummaryOut)
async def get_playlist_summary(
    playlist_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    ensure: bool = Query(default=True),
) -> PlaylistCourseSummaryOut:
    """Return coverage-aware course synthesis (partial/complete)."""
    request_id = getattr(request.state, "request_id", None)
    access = AccessService(db)
    playlist = await access.get_playlist_for_caller(ctx, playlist_id)
    if playlist is None:
        not_found(request_id)

    service = PlaylistSynthesisService(db, settings)
    try:
        result = await service.get_summary(
            workspace_id=ctx.workspace.id,
            playlist_id=playlist_id,
        )
        if result is None and ensure:
            result = await service.synthesize(
                workspace_id=ctx.workspace.id,
                playlist_id=playlist_id,
            )
    except PlaylistSynthesisError as exc:
        raise_api_error(
            exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    if result is None:
        raise_api_error(
            404,
            code="PLAYLIST_SUMMARY_NOT_READY",
            message="Course synthesis is not available yet. Run synthesize first.",
            request_id=request_id,
        )

    return _course_summary_out(result.summary, cache_hit=result.cache_hit)


def _course_summary_out(row: Summary, *, cache_hit: bool) -> PlaylistCourseSummaryOut:
    content: dict[str, Any] = dict(row.content_json or {})
    cov: dict[str, Any] = dict(row.coverage_json or {})
    return PlaylistCourseSummaryOut(
        id=row.id,
        workspace_id=row.workspace_id,
        playlist_id=row.scope_id,
        summary_kind=row.summary_kind,
        status=row.status,
        coverage_label=str(cov.get("coverage_label") or "partial"),
        coverage_ratio=float(cov.get("coverage_ratio") or 0.0),
        included_count=int(cov.get("included_count") or 0),
        excluded_count=int(cov.get("excluded_count") or 0),
        total_count=int(cov.get("total_count") or 0),
        included_video_ids=[str(x) for x in (cov.get("included_video_ids") or [])],
        excluded_video_ids=[str(x) for x in (cov.get("excluded_video_ids") or [])],
        source_revisions={
            str(k): int(v) for k, v in (cov.get("source_revisions") or {}).items()
        },
        caveat=str(cov.get("caveat")) if cov.get("caveat") is not None else None,
        overview=str(content.get("overview") or content.get("summary") or ""),
        topic_modules=[
            TopicModuleOut(**m) for m in (content.get("topic_modules") or []) if isinstance(m, dict)
        ],
        learning_map=[
            LearningMapNodeOut(**n)
            for n in (content.get("learning_map") or [])
            if isinstance(n, dict)
        ],
        cross_video_concepts=[
            CrossVideoConceptOut(**c)
            for c in (content.get("cross_video_concepts") or [])
            if isinstance(c, dict)
        ],
        redundant_topics=[
            RedundantTopicOut(**r)
            for r in (content.get("redundant_topics") or [])
            if isinstance(r, dict)
        ],
        key_takeaways=[
            PlaylistTakeawayOut(**t)
            for t in (content.get("key_takeaways") or [])
            if isinstance(t, dict)
        ],
        origin=str(content.get("origin")) if content.get("origin") is not None else None,
        cache_hit=cache_hit,
        video_cache_hits=int(cov.get("video_cache_hits") or 0),
        provider_run_id=row.provider_run_id,
    )
