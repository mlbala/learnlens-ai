"""GET /api/v1/usage — workspace usage dashboard (estimates clearly labeled)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAuth, get_db
from app.api.v1.schemas import UsageResponse
from app.core.observability.metrics import get_worker_metrics
from app.core.settings import Settings, get_settings
from app.services.usage import UsageService

router = APIRouter(prefix="/api/v1", tags=["usage"])


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    request: Request,
    ctx: CurrentAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    period: Annotated[
        str | None,
        Query(description="Usage period YYYY-MM (defaults to current UTC month)"),
    ] = None,
) -> UsageResponse:
    """Return counts, quotas, and estimated cost for the authenticated workspace."""
    service = UsageService(db, settings)
    snap = await service.snapshot(ctx.workspace.id, period=period)
    body = snap.as_dict()
    body["request_id"] = getattr(request.state, "request_id", None)
    body["worker_metrics"] = get_worker_metrics().snapshot()
    return UsageResponse.model_validate(body)
