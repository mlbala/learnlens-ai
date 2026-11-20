"""Add chat threads, messages, and message citations for grounded QA.

Revision ID: 20261120_0005
Revises: 20261120_0004
Create Date: 2026-11-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261120_0005"
down_revision: str | None = "20261120_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("scope_kind", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_chat_threads_created_by_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_chat_threads_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_threads"),
    )
    op.create_index("ix_chat_threads_workspace_id", "chat_threads", ["workspace_id"])
    op.create_index("ix_chat_threads_scope_id", "chat_threads", ["scope_id"])
    op.create_index("ix_chat_threads_created_by", "chat_threads", ["created_by"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("explanation_mode", sa.String(length=32), nullable=True),
        sa.Column("provider_run_id", sa.Uuid(), nullable=True),
        sa.Column("confidence_label", sa.String(length=32), nullable=True),
        sa.Column("unsupported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_run_id"],
            ["provider_runs.id"],
            name="fk_chat_messages_provider_run_id_provider_runs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_chat_messages_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_chat_messages_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])
    op.create_index("ix_chat_messages_workspace_id", "chat_messages", ["workspace_id"])

    op.create_table(
        "message_citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("segment_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("citation_key", sa.String(length=32), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("timing_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("youtube_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name="fk_message_citations_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["transcript_segments.id"],
            name="fk_message_citations_segment_id_transcript_segments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name="fk_message_citations_video_id_videos",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_message_citations_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_message_citations"),
    )
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"])
    op.create_index("ix_message_citations_workspace_id", "message_citations", ["workspace_id"])
    op.create_index("ix_message_citations_segment_id", "message_citations", ["segment_id"])
    op.create_index("ix_message_citations_video_id", "message_citations", ["video_id"])


def downgrade() -> None:
    op.drop_index("ix_message_citations_video_id", table_name="message_citations")
    op.drop_index("ix_message_citations_segment_id", table_name="message_citations")
    op.drop_index("ix_message_citations_workspace_id", table_name="message_citations")
    op.drop_index("ix_message_citations_message_id", table_name="message_citations")
    op.drop_table("message_citations")
    op.drop_index("ix_chat_messages_workspace_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_threads_created_by", table_name="chat_threads")
    op.drop_index("ix_chat_threads_scope_id", table_name="chat_threads")
    op.drop_index("ix_chat_threads_workspace_id", table_name="chat_threads")
    op.drop_table("chat_threads")
