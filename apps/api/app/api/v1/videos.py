"""Minimal workspace-scoped video read for auth/IDOR coverage (no YouTube import)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import CurrentAuth, DbSession
from app.api.v1.schemas import VideoOut
from app.core.errors import not_found
from app.services.access import AccessService

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


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
    return VideoOut.model_validate(video)
