"""Recover stuck running jobs whose lease has expired."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability.metrics import get_worker_metrics
from app.db.models import IngestionJob
from app.domain.job_states import JobStage, JobStatus

logger = logging.getLogger("learnlens.job_recovery")


async def recover_expired_leases(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 50,
) -> list[uuid.UUID]:
    """
    Re-queue jobs stuck in `running` past `lease_until`.

    Does not re-execute side effects — workers must remain idempotent via
    content hashes / unique keys.
    """
    clock = now or datetime.now(UTC)
    result = await session.execute(
        select(IngestionJob)
        .where(
            IngestionJob.status == JobStatus.RUNNING,
            IngestionJob.lease_until.is_not(None),
            IngestionJob.lease_until < clock,
        )
        .limit(limit)
    )
    recovered: list[uuid.UUID] = []
    for job in result.scalars().all():
        job.status = JobStatus.QUEUED
        job.stage = JobStage.PENDING
        job.last_error_code = "JOB_LEASE_EXPIRED"
        job.lease_until = None
        job.percent = 0
        recovered.append(job.id)
        get_worker_metrics().record_recovery()
        logger.info(
            "job_lease_recovered",
            extra={
                "job_id": str(job.id),
                "workspace_id": str(job.workspace_id),
                "error_code": "JOB_LEASE_EXPIRED",
            },
        )
    if recovered:
        await session.flush()
    return recovered
