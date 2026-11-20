"""Chat threads, messages, and server-resolved citations (phase 08)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import GUID, Base, TimestampMixin, utcnow


class ChatThread(Base, TimestampMixin):
    __tablename__ = "chat_threads"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope_kind: Mapped[str] = mapped_column(String(32), nullable=False)  # video|playlist|library
    scope_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("provider_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unsupported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class MessageCitation(Base):
    __tablename__ = "message_citations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("transcript_segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    citation_key: Mapped[str] = mapped_column(String(32), nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timing_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    youtube_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
