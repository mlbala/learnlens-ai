"""Stamp lesson segments with the chat thread and record search per turn.

Revision ID: 20261122_0011
Revises: 20261122_0010
Create Date: 2026-11-22

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_0011"
down_revision: str | None = "20261122_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transcript_segments",
        sa.Column("thread_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_transcript_segments_thread_id_chat_threads",
        "transcript_segments",
        "chat_threads",
        ["thread_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_transcript_segments_thread_id",
        "transcript_segments",
        ["thread_id"],
    )
    op.add_column(
        "chat_messages",
        sa.Column("external_search_enabled", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "external_search_enabled")
    op.drop_index("ix_transcript_segments_thread_id", table_name="transcript_segments")
    op.drop_constraint(
        "fk_transcript_segments_thread_id_chat_threads",
        "transcript_segments",
        type_="foreignkey",
    )
    op.drop_column("transcript_segments", "thread_id")
