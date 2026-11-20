"""Playlist repository — always scopes by workspace_id."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Playlist, PlaylistItem


class PlaylistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_youtube_id(
        self,
        *,
        workspace_id: uuid.UUID,
        youtube_playlist_id: str,
    ) -> Playlist | None:
        result = await self._session.execute(
            select(Playlist).where(
                Playlist.workspace_id == workspace_id,
                Playlist.youtube_playlist_id == youtube_playlist_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_in_workspace(
        self,
        *,
        playlist_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Playlist | None:
        result = await self._session.execute(
            select(Playlist).where(
                Playlist.id == playlist_id,
                Playlist.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        workspace_id: uuid.UUID,
        youtube_playlist_id: str,
        title: str,
        status: str,
        total_items: int,
    ) -> Playlist:
        existing = await self.get_by_youtube_id(
            workspace_id=workspace_id,
            youtube_playlist_id=youtube_playlist_id,
        )
        if existing is None:
            playlist = Playlist(
                workspace_id=workspace_id,
                youtube_playlist_id=youtube_playlist_id,
                title=title,
                status=status,
                total_items=total_items,
            )
            self._session.add(playlist)
            await self._session.flush()
            return playlist
        existing.title = title
        existing.status = status
        existing.total_items = total_items
        await self._session.flush()
        return existing

    async def replace_items(
        self,
        *,
        playlist_id: uuid.UUID,
        items: list[PlaylistItem],
    ) -> list[PlaylistItem]:
        await self._session.execute(
            delete(PlaylistItem).where(PlaylistItem.playlist_id == playlist_id)
        )
        for item in items:
            self._session.add(item)
        await self._session.flush()
        return items

    async def list_items(self, *, playlist_id: uuid.UUID) -> list[PlaylistItem]:
        result = await self._session.execute(
            select(PlaylistItem)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.playlist_position.asc())
        )
        return list(result.scalars().all())

    async def list_in_workspace(
        self,
        *,
        workspace_id: uuid.UUID,
        limit: int = 50,
    ) -> list[Playlist]:
        limit = min(max(limit, 1), 100)
        result = await self._session.execute(
            select(Playlist)
            .where(Playlist.workspace_id == workspace_id)
            .order_by(Playlist.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_items_ready_for_video(self, *, video_id: uuid.UUID) -> int:
        """Flip playlist membership to ready after a permitted transcript lands."""
        result = await self._session.execute(
            update(PlaylistItem)
            .where(
                PlaylistItem.video_id == video_id,
                PlaylistItem.state.in_(["needs_transcript", "pending", "queued", "processing"]),
            )
            .values(state="ready")
        )
        await self._session.flush()
        return int(result.rowcount or 0)
