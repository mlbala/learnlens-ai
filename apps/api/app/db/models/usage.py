"""Per-workspace usage counters and period caps (phase 15)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, utcnow


class UsageLimit(Base):
    """
    Server-side workspace usage ledger for a billing/usage period (e.g. YYYY-MM).

    Caps are enforced in application transactions; this table is the durable counter.
    """

    __tablename__ = "usage_limits"
    __table_args__ = (
        UniqueConstraint("workspace_id", "period", name="uq_usage_limits_workspace_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. 2026-11
    jobs_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_spend_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    jobs_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    tokens_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=2_000_000)
    requests_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=10_000)
    spend_cap_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("25")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
