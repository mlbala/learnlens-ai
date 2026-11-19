"""Video repository — always scopes by workspace_id (never trust client workspace)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Video


class VideoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_fixture(
        self,
        *,
        workspace_id: uuid.UUID,
        youtube_video_id: str,
        title: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> Video:
        """Insert fixture/demo video rows only (marked in metadata)."""
        meta = dict(metadata_json or {})
        meta.setdefault("fixture_data", True)
        video = Video(
            workspace_id=workspace_id,
            youtube_video_id=youtube_video_id,
            title=title,
            status="fixture",
            metadata_json=meta,
        )
        self._session.add(video)
        await self._session.flush()
        return video

    async def get_in_workspace(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Video | None:
        result = await self._session.execute(
            select(Video).where(
                Video.id == video_id,
                Video.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_youtube_id(
        self,
        *,
        workspace_id: uuid.UUID,
        youtube_video_id: str,
    ) -> Video | None:
        result = await self._session.execute(
            select(Video).where(
                Video.workspace_id == workspace_id,
                Video.youtube_video_id == youtube_video_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_unscoped(self, video_id: uuid.UUID) -> Video | None:
        """Lookup without workspace filter — for IDOR negative tests only."""
        return await self._session.get(Video, video_id)

    async def list_in_workspace(
        self,
        *,
        workspace_id: uuid.UUID,
        limit: int = 50,
        status: str | None = None,
    ) -> list[Video]:
        limit = min(max(limit, 1), 100)
        stmt = select(Video).where(Video.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(Video.status == status)
        stmt = stmt.order_by(Video.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_from_metadata(
        self,
        *,
        workspace_id: uuid.UUID,
        youtube_video_id: str,
        title: str,
        channel_title: str | None,
        duration_seconds: int | None,
        source_url: str,
        status: str,
        metadata_json: dict[str, Any] | None,
    ) -> tuple[Video, bool]:
        """
        Insert or update by (workspace_id, youtube_video_id).

        Returns (video, created). Never promotes status to summarized/ready from metadata alone.
        """
        existing = await self.get_by_youtube_id(
            workspace_id=workspace_id,
            youtube_video_id=youtube_video_id,
        )
        if existing is None:
            video = Video(
                workspace_id=workspace_id,
                youtube_video_id=youtube_video_id,
                title=title,
                channel_title=channel_title,
                duration_seconds=duration_seconds,
                source_url=source_url,
                status=status,
                metadata_json=metadata_json,
            )
            self._session.add(video)
            await self._session.flush()
            return video, True

        # Do not overwrite advanced processing states with a bare re-import.
        protected = {
            "queued",
            "validating",
            "normalizing",
            "segmenting",
            "summarizing",
            "indexing",
            "ready",
        }
        existing.title = title or existing.title
        existing.channel_title = channel_title
        existing.duration_seconds = duration_seconds
        existing.source_url = source_url
        existing.metadata_json = metadata_json
        if existing.status not in protected:
            existing.status = status
        await self._session.flush()
        return existing, False
