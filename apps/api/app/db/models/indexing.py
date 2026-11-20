"""Index manifests — track derived Qdrant collections per video/profile."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, TimestampMixin


class IndexManifest(Base, TimestampMixin):
    __tablename__ = "index_manifests"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "video_id",
            "embedding_profile",
            "source_revision",
            name="uq_index_manifests_video_profile_revision",
        ),
    )

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
    embedding_profile: Mapped[str] = mapped_column(String(200), nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    qdrant_collection: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    processing_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Previous collection retained until the new profile is validated (safe reindex).
    previous_collection: Mapped[str | None] = mapped_column(String(255), nullable=True)
