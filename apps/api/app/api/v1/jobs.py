"""GET /api/v1/jobs/{job_id} — workspace-scoped job status."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import CurrentAuth, DbSession
from app.api.v1.schemas import JobOut
from app.core.errors import not_found
from app.db.repositories import IngestionJobRepository

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
) -> JobOut:
    """Return job status only when it belongs to the caller's workspace."""
    repo = IngestionJobRepository(db)
    job = await repo.get_in_workspace(job_id=job_id, workspace_id=ctx.workspace.id)
    if job is None:
        not_found(getattr(request.state, "request_id", None))
    return JobOut.model_validate(job)
