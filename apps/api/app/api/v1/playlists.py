"""Playlist metadata import and workspace-scoped reads."""

from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, Query, Request

from app.api.deps import CsrfAuth, CurrentAuth, DbSession, SettingsDep
from app.api.v1.schemas import (
    ImportNoticeOut,
    PlaylistImportResponse,
    PlaylistItemOut,
    PlaylistListItemOut,
    PlaylistListResponse,
    PlaylistOut,
    YoutubeImportRequest,
)
from app.core.errors import not_found, raise_api_error
from app.db.models import Playlist, PlaylistItem
from app.services.access import AccessService
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
