"""Authorized media assets and extracted frames (opt-in phase 17)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import GUID, Base, TimestampMixin, utcnow


class MediaAsset(Base, TimestampMixin):
    """User-owned/licensed audio or video stored privately (not YouTube downloads)."""

    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # audio | video
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    rights_attested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_transfer_consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True
    )
    antivirus_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    # Derived SourceAsset created after STT alignment (licensed_media).
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("source_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Provenance / cost / confidence aggregates — never raw transcript text.
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class MediaFrame(Base):
    """Extracted frame/diagram with optional verified time anchor."""

    __tablename__ = "media_frames"
    __table_args__ = (
        UniqueConstraint("media_asset_id", "ordinal", name="uq_media_frames_asset_ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="frame")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    alignment_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    provenance: Mapped[str] = mapped_column(String(64), nullable=False, default="fixture_data")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
