"""Ingestion job repository — idempotency key lookups."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IngestionJob


class IngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(self, key: str) -> IngestionJob | None:
        result = await self._session.execute(
            select(IngestionJob).where(IngestionJob.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def create_succeeded(
        self,
        *,
        workspace_id: uuid.UUID,
        job_type: str,
        idempotency_key: str,
        result_resource_id: uuid.UUID,
        video_id: uuid.UUID | None = None,
    ) -> IngestionJob:
        job = IngestionJob(
            workspace_id=workspace_id,
            video_id=video_id,
            job_type=job_type,
            status="succeeded",
            stage="metadata",
            attempt=1,
            idempotency_key=idempotency_key,
            percent=100,
            result_resource_id=result_resource_id,
        )
        self._session.add(job)
        await self._session.flush()
        return job
