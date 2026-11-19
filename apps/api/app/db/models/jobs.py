"""Ingestion jobs and optional outbox events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import GUID, Base, TimestampMixin, utcnow


class IngestionJob(Base, TimestampMixin):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_ingestion_jobs_idempotency"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("source_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Phase 04: store imported video/playlist UUID for Idempotency-Key replay.
    result_resource_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    event_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
