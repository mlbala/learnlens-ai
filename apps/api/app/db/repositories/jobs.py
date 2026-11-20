"""Ingestion job repository — idempotency key lookups and state transitions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IngestionJob
from app.domain.job_states import can_transition, stage_percent


class InvalidJobTransition(ValueError):
    def __init__(self, from_status: str, from_stage: str, to_status: str, to_stage: str) -> None:
        super().__init__(
            f"Illegal job transition {from_status}/{from_stage} -> {to_status}/{to_stage}"
        )
        self.from_status = from_status
        self.from_stage = from_stage
        self.to_status = to_status
        self.to_stage = to_stage


class IngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(self, key: str) -> IngestionJob | None:
        result = await self._session.execute(
            select(IngestionJob).where(IngestionJob.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_in_workspace(
        self,
        *,
        job_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> IngestionJob | None:
        result = await self._session.execute(
            select(IngestionJob).where(
                IngestionJob.id == job_id,
                IngestionJob.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, job_id: uuid.UUID) -> IngestionJob | None:
        return await self._session.get(IngestionJob, job_id)

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

    async def create_queued(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID | None,
        source_asset_id: uuid.UUID | None,
        job_type: str,
        idempotency_key: str,
        result_resource_id: uuid.UUID | None = None,
    ) -> IngestionJob:
        job = IngestionJob(
            workspace_id=workspace_id,
            video_id=video_id,
            source_asset_id=source_asset_id,
            job_type=job_type,
            status="queued",
            stage="pending",
            attempt=0,
            idempotency_key=idempotency_key,
            percent=0,
            result_resource_id=result_resource_id,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def transition(
        self,
        job: IngestionJob,
        *,
        status: str,
        stage: str,
        last_error_code: str | None = None,
        clear_error: bool = False,
        increment_attempt: bool = False,
        lease_until: datetime | None = None,
        source_asset_id: uuid.UUID | None = None,
        result_resource_id: uuid.UUID | None = None,
    ) -> IngestionJob:
        if not can_transition(
            from_status=job.status,
            from_stage=job.stage,
            to_status=status,
            to_stage=stage,
        ):
            raise InvalidJobTransition(job.status, job.stage, status, stage)
        job.status = status
        job.stage = stage
        job.percent = stage_percent(status, stage)
        if clear_error:
            job.last_error_code = None
        elif last_error_code is not None:
            job.last_error_code = last_error_code
        if increment_attempt:
            job.attempt += 1
        if lease_until is not None:
            job.lease_until = lease_until
        if source_asset_id is not None:
            job.source_asset_id = source_asset_id
        if result_resource_id is not None:
            job.result_resource_id = result_resource_id
        await self._session.flush()
        return job
