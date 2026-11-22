"""Outside-search hits for one lesson thread. Not transcript segments."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, utcnow


class ExternalEvidence(Base):
    """One URL returned by the searcher on a turn whose checkbox was on."""

    __tablename__ = "external_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_origin = 'external_search'",
            name="origin_external_search",
        ),
        CheckConstraint(
            "evidence_provider IN ('tavily', 'semantic_scholar', 'openalex')",
            name="provider_known",
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
    thread_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_origin: Mapped[str] = mapped_column(
        String(32), nullable=False, default="external_search"
    )
    evidence_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
