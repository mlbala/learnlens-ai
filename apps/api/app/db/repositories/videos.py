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

    async def get_by_id_unscoped(self, video_id: uuid.UUID) -> Video | None:
        """Lookup without workspace filter — for IDOR negative tests only."""
        return await self._session.get(Video, video_id)
