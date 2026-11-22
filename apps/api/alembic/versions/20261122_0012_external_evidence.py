"""Outside-search hits for a lesson thread.

Revision ID: 20261122_0012
Revises: 20261122_0011
Create Date: 2026-11-22

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_0012"
down_revision: str | None = "20261122_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_origin", sa.String(length=32), nullable=False),
        sa.Column("evidence_provider", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_origin = 'external_search'",
            name="ck_external_evidence_origin_external_search",
        ),
        sa.CheckConstraint(
            "evidence_provider IN ('tavily', 'semantic_scholar', 'openalex')",
            name="ck_external_evidence_provider_known",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_external_evidence_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name="fk_external_evidence_video_id_videos",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_external_evidence_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name="fk_external_evidence_message_id_chat_messages",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_external_evidence"),
    )
    op.create_index(
        "ix_external_evidence_workspace_id",
        "external_evidence",
        ["workspace_id"],
    )
    op.create_index("ix_external_evidence_video_id", "external_evidence", ["video_id"])
    op.create_index("ix_external_evidence_thread_id", "external_evidence", ["thread_id"])
    op.create_index(
        "ix_external_evidence_message_id",
        "external_evidence",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_evidence_message_id", table_name="external_evidence")
    op.drop_index("ix_external_evidence_thread_id", table_name="external_evidence")
    op.drop_index("ix_external_evidence_video_id", table_name="external_evidence")
    op.drop_index("ix_external_evidence_workspace_id", table_name="external_evidence")
    op.drop_table("external_evidence")
