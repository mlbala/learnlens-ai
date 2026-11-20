"""Workspace quota enforcement and usage dashboard aggregation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability.cost import (
    COST_ESTIMATE_DISCLAIMER,
    COST_ESTIMATE_VERSION,
)
from app.core.settings import Settings
from app.db.models import IngestionJob, ProviderRun
from app.db.models.usage import UsageLimit
from app.db.repositories.usage import UsageLimitRepository


class WorkspaceQuotaExceeded(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    period: str
    jobs_used: int
    tokens_used: int
    requests_used: int
    estimated_spend_usd: float
    jobs_cap: int
    tokens_cap: int
    requests_cap: int
    spend_cap_usd: float
    estimate_version: str
    is_estimate: bool
    disclaimer: str
    provider_run_count: int
    job_status_counts: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "counts": {
                "jobs_used": self.jobs_used,
                "tokens_used": self.tokens_used,
                "requests_used": self.requests_used,
                "provider_runs": self.provider_run_count,
                "jobs_by_status": self.job_status_counts,
            },
            "quotas": {
                "jobs_cap": self.jobs_cap,
                "tokens_cap": self.tokens_cap,
                "requests_cap": self.requests_cap,
                "spend_cap_usd": self.spend_cap_usd,
            },
            "estimated_cost": {
                "estimate_usd": self.estimated_spend_usd,
                "estimate_version": self.estimate_version,
                "is_estimate": self.is_estimate,
                "disclaimer": self.disclaimer,
            },
        }


def current_period(now: datetime | None = None) -> str:
    clock = now or datetime.now(UTC)
    return clock.strftime("%Y-%m")


class UsageService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._limits = UsageLimitRepository(session)

    async def _row(self, workspace_id: uuid.UUID, period: str | None = None) -> UsageLimit:
        return await self._limits.get_or_create(
            workspace_id=workspace_id,
            period=period or current_period(),
            jobs_cap=self._settings.usage_workspace_jobs_cap,
            tokens_cap=self._settings.usage_workspace_tokens_cap,
            requests_cap=self._settings.usage_workspace_requests_cap,
            spend_cap_usd=Decimal(str(self._settings.usage_workspace_spend_cap_usd)),
        )

    async def check_request_allowed(self, workspace_id: uuid.UUID) -> None:
        row = await self._row(workspace_id)
        if row.requests_used >= row.requests_cap:
            raise WorkspaceQuotaExceeded(
                "USAGE_QUOTA_EXCEEDED",
                "Workspace request quota exceeded for this period.",
            )
        if row.estimated_spend_usd >= row.spend_cap_usd:
            raise WorkspaceQuotaExceeded(
                "WORKSPACE_SPEND_QUOTA_EXCEEDED",
                "Workspace estimated spend cap reached for this period.",
            )

    async def check_job_allowed(self, workspace_id: uuid.UUID) -> None:
        row = await self._row(workspace_id)
        if row.jobs_used >= row.jobs_cap:
            raise WorkspaceQuotaExceeded(
                "WORKSPACE_JOB_QUOTA_EXCEEDED",
                "Workspace job quota exceeded for this period.",
            )
        await self.check_request_allowed(workspace_id)

    async def check_tokens_allowed(
        self, workspace_id: uuid.UUID, *, additional_tokens: int
    ) -> None:
        row = await self._row(workspace_id)
        if row.tokens_used + max(0, additional_tokens) > row.tokens_cap:
            raise WorkspaceQuotaExceeded(
                "WORKSPACE_TOKEN_QUOTA_EXCEEDED",
                "Workspace token quota exceeded for this period.",
            )

    async def record_request(self, workspace_id: uuid.UUID) -> None:
        row = await self._row(workspace_id)
        row.requests_used += 1
        await self._session.flush()

    async def record_job(self, workspace_id: uuid.UUID) -> None:
        """Increment job counter once per new job (idempotent callers must skip replays)."""
        row = await self._row(workspace_id)
        row.jobs_used += 1
        row.requests_used += 1
        await self._session.flush()

    async def record_provider_usage(
        self,
        workspace_id: uuid.UUID,
        *,
        token_in: int | None,
        token_out: int | None,
        estimate_usd: float,
        effect_key: str | None = None,
        seen_effect_keys: set[str] | None = None,
    ) -> bool:
        """
        Record token/spend usage. Returns False if `effect_key` was already applied
        (exactly-once *effect* via unique key — not exactly-once execution).
        """
        if effect_key and seen_effect_keys is not None:
            if effect_key in seen_effect_keys:
                return False
            seen_effect_keys.add(effect_key)

        row = await self._row(workspace_id)
        tokens = max(0, int(token_in or 0)) + max(0, int(token_out or 0))
        if row.tokens_used + tokens > row.tokens_cap:
            raise WorkspaceQuotaExceeded(
                "WORKSPACE_TOKEN_QUOTA_EXCEEDED",
                "Workspace token quota exceeded for this period.",
            )
        projected = row.estimated_spend_usd + Decimal(str(estimate_usd))
        if projected > row.spend_cap_usd:
            raise WorkspaceQuotaExceeded(
                "WORKSPACE_SPEND_QUOTA_EXCEEDED",
                "Workspace estimated spend cap reached for this period.",
            )
        row.tokens_used += tokens
        row.estimated_spend_usd = projected
        row.requests_used += 1
        await self._session.flush()
        return True

    async def snapshot(
        self,
        workspace_id: uuid.UUID,
        *,
        period: str | None = None,
    ) -> UsageSnapshot:
        period_key = period or current_period()
        row = await self._row(workspace_id, period_key)

        run_count = await self._session.scalar(
            select(func.count())
            .select_from(ProviderRun)
            .where(ProviderRun.workspace_id == workspace_id)
        )
        status_rows = await self._session.execute(
            select(IngestionJob.status, func.count())
            .where(IngestionJob.workspace_id == workspace_id)
            .group_by(IngestionJob.status)
        )
        status_counts = {str(status): int(count) for status, count in status_rows.all()}

        return UsageSnapshot(
            period=period_key,
            jobs_used=row.jobs_used,
            tokens_used=row.tokens_used,
            requests_used=row.requests_used,
            estimated_spend_usd=float(row.estimated_spend_usd),
            jobs_cap=row.jobs_cap,
            tokens_cap=row.tokens_cap,
            requests_cap=row.requests_cap,
            spend_cap_usd=float(row.spend_cap_usd),
            estimate_version=COST_ESTIMATE_VERSION,
            is_estimate=True,
            disclaimer=COST_ESTIMATE_DISCLAIMER,
            provider_run_count=int(run_count or 0),
            job_status_counts=status_counts,
        )
