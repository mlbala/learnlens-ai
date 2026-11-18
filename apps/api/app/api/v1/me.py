"""Current identity endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentAuth
from app.api.v1.schemas import MeResponse, UserOut, WorkspaceOut

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me", response_model=MeResponse)
async def me(ctx: CurrentAuth) -> MeResponse:
    return MeResponse(
        user=UserOut.model_validate(ctx.user),
        workspace=WorkspaceOut.model_validate(ctx.workspace),
    )
