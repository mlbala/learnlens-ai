"""Workspace usage_limits repository — get-or-create and atomic increments."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.usage import UsageLimit


class UsageLimitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self,
        *,
        workspace_id: uuid.UUID,
        period: str,
        jobs_cap: int,
        tokens_cap: int,
        requests_cap: int,
        spend_cap_usd: Decimal,
    ) -> UsageLimit:
        result = await self._session.execute(
            select(UsageLimit).where(
                UsageLimit.workspace_id == workspace_id,
                UsageLimit.period == period,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row
        row = UsageLimit(
            workspace_id=workspace_id,
            period=period,
            jobs_cap=jobs_cap,
            tokens_cap=tokens_cap,
            requests_cap=requests_cap,
            spend_cap_usd=spend_cap_usd,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(
        self,
        *,
        workspace_id: uuid.UUID,
        period: str,
    ) -> UsageLimit | None:
        result = await self._session.execute(
            select(UsageLimit).where(
                UsageLimit.workspace_id == workspace_id,
                UsageLimit.period == period,
            )
        )
        return result.scalar_one_or_none()
