"""Add tutor/quiz/spaced-review/concept tables (phase 18).

Revision ID: 20261120_0009
Revises: 20261120_0008
Create Date: 2026-11-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261120_0009"
down_revision: str | None = "20261120_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "concepts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_segment_ids", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "canonical_name",
            name="uq_concepts_workspace_canonical_name",
        ),
    )
    op.create_index("ix_concepts_workspace_id", "concepts", ["workspace_id"])
    op.create_index("ix_concepts_video_id", "concepts", ["video_id"])

    op.create_table(
        "concept_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("src_concept_id", sa.Uuid(), nullable=False),
        sa.Column("dst_concept_id", sa.Uuid(), nullable=False),
        sa.Column(
            "relation",
            sa.String(length=64),
            nullable=False,
            server_default="prerequisite",
        ),
        sa.Column("evidence_span_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dst_concept_id"], ["concepts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_span_id"],
            ["transcript_segments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["src_concept_id"], ["concepts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "src_concept_id",
            "dst_concept_id",
            "relation",
            name="uq_concept_edges_src_dst_relation",
        ),
    )
    op.create_index("ix_concept_edges_workspace_id", "concept_edges", ["workspace_id"])
    op.create_index(
        "ix_concept_edges_src_concept_id", "concept_edges", ["src_concept_id"]
    )
    op.create_index(
        "ix_concept_edges_dst_concept_id", "concept_edges", ["dst_concept_id"]
    )

    op.create_table(
        "study_decks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column(
            "presentation_language",
            sa.String(length=8),
            nullable=False,
            server_default="en",
        ),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="ready"
        ),
        sa.Column(
            "origin",
            sa.String(length=64),
            nullable=False,
            server_default="fixture_data",
        ),
        sa.Column("provider_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_run_id"], ["provider_runs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_decks_workspace_id", "study_decks", ["workspace_id"])
    op.create_index("ix_study_decks_user_id", "study_decks", ["user_id"])
    op.create_index("ix_study_decks_video_id", "study_decks", ["video_id"])

    op.create_table(
        "study_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deck_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("item_kind", sa.String(length=32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "explanation_origin",
            sa.String(length=64),
            nullable=False,
            server_default="source_supported",
        ),
        sa.Column("choices_json", sa.JSON(), nullable=True),
        sa.Column("correct_choice_index", sa.Integer(), nullable=True),
        sa.Column("evidence_segment_ids", sa.JSON(), nullable=False),
        sa.Column("presentation_json", sa.JSON(), nullable=True),
        sa.Column("concept_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["concept_id"], ["concepts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["deck_id"], ["study_decks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deck_id", "ordinal", name="uq_study_items_deck_ordinal"),
    )
    op.create_index("ix_study_items_deck_id", "study_items", ["deck_id"])
    op.create_index("ix_study_items_workspace_id", "study_items", ["workspace_id"])
    op.create_index("ix_study_items_user_id", "study_items", ["user_id"])

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("deck_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("selected_choice_index", sa.Integer(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("evidence_resolved", sa.Boolean(), nullable=False),
        sa.Column("evidence_segment_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["deck_id"], ["study_decks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["study_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_attempts_workspace_id", "quiz_attempts", ["workspace_id"])
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_deck_id", "quiz_attempts", ["deck_id"])
    op.create_index("ix_quiz_attempts_item_id", "quiz_attempts", ["item_id"])

    op.create_table(
        "review_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_days", sa.Float(), nullable=False),
        sa.Column("ease_factor", sa.Float(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column("last_result", sa.String(length=32), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["study_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            "item_id",
            name="uq_review_schedules_user_item",
        ),
    )
    op.create_index(
        "ix_review_schedules_workspace_id", "review_schedules", ["workspace_id"]
    )
    op.create_index("ix_review_schedules_user_id", "review_schedules", ["user_id"])
    op.create_index("ix_review_schedules_item_id", "review_schedules", ["item_id"])
    op.create_index("ix_review_schedules_due_at", "review_schedules", ["due_at"])

    op.create_table(
        "learner_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=True),
        sa.Column("deck_id", sa.Uuid(), nullable=True),
        sa.Column("items_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "reviews_completed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "disclaimer",
            sa.String(length=200),
            nullable=False,
            server_default=(
                "Practice counts only — no learning-efficacy claim without evaluation."
            ),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["deck_id"], ["study_decks.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            "video_id",
            name="uq_learner_progress_user_video",
        ),
    )
    op.create_index(
        "ix_learner_progress_workspace_id", "learner_progress", ["workspace_id"]
    )
    op.create_index("ix_learner_progress_user_id", "learner_progress", ["user_id"])
    op.create_index("ix_learner_progress_video_id", "learner_progress", ["video_id"])

    op.create_table(
        "tutor_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "presentation_language",
            sa.String(length=8),
            nullable=False,
            server_default="en",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_tutor_preferences_workspace_user",
        ),
    )
    op.create_index(
        "ix_tutor_preferences_workspace_id", "tutor_preferences", ["workspace_id"]
    )
    op.create_index("ix_tutor_preferences_user_id", "tutor_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_tutor_preferences_user_id", table_name="tutor_preferences")
    op.drop_index("ix_tutor_preferences_workspace_id", table_name="tutor_preferences")
    op.drop_table("tutor_preferences")

    op.drop_index("ix_learner_progress_video_id", table_name="learner_progress")
    op.drop_index("ix_learner_progress_user_id", table_name="learner_progress")
    op.drop_index("ix_learner_progress_workspace_id", table_name="learner_progress")
    op.drop_table("learner_progress")

    op.drop_index("ix_review_schedules_due_at", table_name="review_schedules")
    op.drop_index("ix_review_schedules_item_id", table_name="review_schedules")
    op.drop_index("ix_review_schedules_user_id", table_name="review_schedules")
    op.drop_index("ix_review_schedules_workspace_id", table_name="review_schedules")
    op.drop_table("review_schedules")

    op.drop_index("ix_quiz_attempts_item_id", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_deck_id", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_workspace_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")

    op.drop_index("ix_study_items_user_id", table_name="study_items")
    op.drop_index("ix_study_items_workspace_id", table_name="study_items")
    op.drop_index("ix_study_items_deck_id", table_name="study_items")
    op.drop_table("study_items")

    op.drop_index("ix_study_decks_video_id", table_name="study_decks")
    op.drop_index("ix_study_decks_user_id", table_name="study_decks")
    op.drop_index("ix_study_decks_workspace_id", table_name="study_decks")
    op.drop_table("study_decks")

    op.drop_index("ix_concept_edges_dst_concept_id", table_name="concept_edges")
    op.drop_index("ix_concept_edges_src_concept_id", table_name="concept_edges")
    op.drop_index("ix_concept_edges_workspace_id", table_name="concept_edges")
    op.drop_table("concept_edges")

    op.drop_index("ix_concepts_video_id", table_name="concepts")
    op.drop_index("ix_concepts_workspace_id", table_name="concepts")
    op.drop_table("concepts")
