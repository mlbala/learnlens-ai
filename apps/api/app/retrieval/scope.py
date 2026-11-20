"""Resolve authorized video IDs from Neon (SQL) — never trust browser filters."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Playlist, PlaylistItem, Video
from app.retrieval.errors import UnauthorizedScopeError
from app.retrieval.filters import parse_uuid, reject_freeform_filter

ScopeKind = Literal["video", "playlist", "library"]


@dataclass(frozen=True, slots=True)
class AuthorizedScope:
    workspace_id: uuid.UUID
    scope_kind: ScopeKind
    scope_id: uuid.UUID | None
    video_ids: tuple[uuid.UUID, ...]


async def resolve_authorized_video_ids(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    scope_kind: ScopeKind,
    scope_id: uuid.UUID | None = None,
    client_filter: object = None,
) -> AuthorizedScope:
    """
    Derive exact allowed video IDs from SQL ownership.

    `client_filter` is rejected if present — Qdrant filters are never client-supplied.
    """
    reject_freeform_filter(client_filter)
    ws = parse_uuid(workspace_id, field_name="workspace_id")

    if scope_kind == "video":
        if scope_id is None:
            raise UnauthorizedScopeError(
                "video scope requires scope_id.",
                details={"scope_kind": scope_kind},
            )
        video = await db.scalar(select(Video).where(Video.id == scope_id, Video.workspace_id == ws))
        if video is None:
            raise UnauthorizedScopeError(
                "Video is not in the authenticated workspace.",
                details={"scope_kind": scope_kind},
            )
        return AuthorizedScope(
            workspace_id=ws,
            scope_kind="video",
            scope_id=scope_id,
            video_ids=(video.id,),
        )

    if scope_kind == "playlist":
        if scope_id is None:
            raise UnauthorizedScopeError(
                "playlist scope requires scope_id.",
                details={"scope_kind": scope_kind},
            )
        playlist = await db.scalar(
            select(Playlist).where(Playlist.id == scope_id, Playlist.workspace_id == ws)
        )
        if playlist is None:
            raise UnauthorizedScopeError(
                "Playlist is not in the authenticated workspace.",
                details={"scope_kind": scope_kind},
            )
        rows = await db.execute(
            select(PlaylistItem.video_id)
            .where(
                PlaylistItem.playlist_id == playlist.id,
                PlaylistItem.video_id.is_not(None),
            )
            .order_by(PlaylistItem.playlist_position.asc())
        )
        video_ids = tuple(vid for vid in rows.scalars().all() if vid is not None)
        # Defense in depth: only keep videos that still belong to the workspace.
        if video_ids:
            owned = await db.execute(
                select(Video.id).where(
                    Video.workspace_id == ws,
                    Video.id.in_(video_ids),
                )
            )
            owned_set = set(owned.scalars().all())
            video_ids = tuple(v for v in video_ids if v in owned_set)
        if not video_ids:
            raise UnauthorizedScopeError(
                "Playlist has no authorized videos with content scope.",
                details={"scope_kind": scope_kind},
            )
        return AuthorizedScope(
            workspace_id=ws,
            scope_kind="playlist",
            scope_id=scope_id,
            video_ids=video_ids,
        )

    if scope_kind == "library":
        rows = await db.execute(
            select(Video.id).where(Video.workspace_id == ws).order_by(Video.created_at.desc())
        )
        video_ids = tuple(rows.scalars().all())
        if not video_ids:
            raise UnauthorizedScopeError(
                "Library has no videos in this workspace.",
                details={"scope_kind": scope_kind},
            )
        return AuthorizedScope(
            workspace_id=ws,
            scope_kind="library",
            scope_id=None,
            video_ids=video_ids,
        )

    raise UnauthorizedScopeError(
        f"Unsupported scope_kind '{scope_kind}'.",
        details={"scope_kind": scope_kind},
    )
