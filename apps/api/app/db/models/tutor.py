"""Adaptive tutoring, quizzes, spaced review, and concept graph (phase 18).

Postgres only — no Neo4j. Progress and generated content are user+workspace scoped.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import GUID, Base, TimestampMixin, utcnow


class Concept(Base, TimestampMixin):
    """Workspace concept node — optional evidence links; not a learning-efficacy claim."""

    __tablename__ = "concepts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "canonical_name",
            name="uq_concepts_workspace_canonical_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("videos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_segment_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ConceptEdge(Base):
    """Directed concept link (e.g. prerequisite). Stored in Postgres, not Neo4j."""

    __tablename__ = "concept_edges"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "src_concept_id",
            "dst_concept_id",
            "relation",
            name="uq_concept_edges_src_dst_relation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    src_concept_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dst_concept_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation: Mapped[str] = mapped_column(String(64), nullable=False, default="prerequisite")
    evidence_span_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class StudyDeck(Base, TimestampMixin):
    """Generated flashcard/quiz deck for one video, owned by a user in a workspace."""

    __tablename__ = "study_decks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    presentation_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    origin: Mapped[str] = mapped_column(String(64), nullable=False, default="fixture_data")
    provider_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("provider_runs.id", ondelete="SET NULL"),
        nullable=True,
    )


class StudyItem(Base, TimestampMixin):
    """Flashcard or quiz question with server-validated evidence segment IDs."""

    __tablename__ = "study_items"
    __table_args__ = (
        UniqueConstraint("deck_id", "ordinal", name="uq_study_items_deck_ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    deck_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("study_decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_kind: Mapped[str] = mapped_column(String(32), nullable=False)  # flashcard|quiz
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation_origin: Mapped[str] = mapped_column(
        String(64), nullable=False, default="source_supported"
    )
    choices_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    correct_choice_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_segment_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    presentation_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("concepts.id", ondelete="SET NULL"),
        nullable=True,
    )


class QuizAttempt(Base):
    """Per-user quiz attempt — answers resolve to stored evidence IDs."""

    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deck_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("study_decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("study_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    selected_choice_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_segment_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ReviewSchedule(Base, TimestampMixin):
    """Simple spaced-review schedule (SM-2 lite) per user study item."""

    __tablename__ = "review_schedules"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "item_id",
            name="uq_review_schedules_user_item",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("study_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_days: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LearnerProgress(Base, TimestampMixin):
    """Aggregated practice progress — isolated by user + workspace."""

    __tablename__ = "learner_progress"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "video_id",
            name="uq_learner_progress_user_video",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    deck_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("study_decks.id", ondelete="SET NULL"),
        nullable=True,
    )
    items_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviews_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Never claim measured learning gains; store counts only.
    disclaimer: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="Practice counts only — no learning-efficacy claim without evaluation.",
    )


class TutorPreference(Base, TimestampMixin):
    """Presentation language preference (en|ta); evidence stays in original language."""

    __tablename__ = "tutor_preferences"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_tutor_preferences_workspace_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    presentation_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
