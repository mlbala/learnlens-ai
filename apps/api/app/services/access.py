"""Server-side workspace authorization (fail closed)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Playlist, PlaylistItem, Video
from app.db.repositories import PlaylistRepository, VideoRepository, WorkspaceRepository
from app.services.auth import AuthContext


class AccessService:
    def __init__(self, db: AsyncSession) -> None:
        self._workspaces = WorkspaceRepository(db)
        self._videos = VideoRepository(db)
        self._playlists = PlaylistRepository(db)

    async def require_workspace_member(self, ctx: AuthContext, workspace_id: uuid.UUID) -> bool:
        """Caller-supplied workspace_id must match authenticated membership."""
        if workspace_id != ctx.workspace.id:
            # Still verify membership so spoofed IDs never pass.
            return await self._workspaces.user_belongs(
                user_id=ctx.user.id,
                workspace_id=workspace_id,
            )
        return True

    async def get_video_for_caller(
        self,
        ctx: AuthContext,
        video_id: uuid.UUID,
    ) -> Video | None:
        """Return video only when it belongs to the caller's workspace."""
        return await self._videos.get_in_workspace(
            video_id=video_id,
            workspace_id=ctx.workspace.id,
        )

    async def list_videos_for_caller(
        self,
        ctx: AuthContext,
        *,
        limit: int = 50,
        status: str | None = None,
    ) -> list[Video]:
        return await self._videos.list_in_workspace(
            workspace_id=ctx.workspace.id,
            limit=limit,
            status=status,
        )

    async def get_playlist_for_caller(
        self,
        ctx: AuthContext,
        playlist_id: uuid.UUID,
    ) -> Playlist | None:
        return await self._playlists.get_in_workspace(
            playlist_id=playlist_id,
            workspace_id=ctx.workspace.id,
        )

    async def list_playlist_items(self, playlist_id: uuid.UUID) -> list[PlaylistItem]:
        return await self._playlists.list_items(playlist_id=playlist_id)
