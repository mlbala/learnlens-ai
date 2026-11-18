"""Test-only seed helpers. Never enabled in production."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.repositories import VideoRepository


async def seed_fixture_video(
    session: AsyncSession,
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    youtube_video_id: str = "dQw4w9WgXcQ",
    title: str = "Fixture lecture (not real YouTube content)",
) -> uuid.UUID:
    """Insert a clearly marked fixture video row for offline tests."""
    if settings.is_production_like() or not settings.allow_test_seed:
        msg = "Fixture seeding is only allowed when ALLOW_TEST_SEED=true outside production"
        raise RuntimeError(msg)
    repo = VideoRepository(session)
    video = await repo.create_fixture(
        workspace_id=workspace_id,
        youtube_video_id=youtube_video_id,
        title=title,
        metadata_json={"fixture_data": True, "note": "synthetic test fixture"},
    )
    return video.id
