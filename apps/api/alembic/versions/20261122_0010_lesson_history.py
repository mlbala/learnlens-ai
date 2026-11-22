"""Workspace lesson history limit and Gemini transcript flags.

Revision ID: 20261122_0010
Revises: 20261120_0009
Create Date: 2026-11-22

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_0010"
down_revision: str | None = "20261120_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "learning_history_limit",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    op.create_check_constraint(
        "ck_workspaces_learning_history_limit",
        "workspaces",
        "learning_history_limit >= 1 AND learning_history_limit <= 100",
    )
    op.add_column(
        "videos",
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "transcript_segments",
        sa.Column("evidence_origin", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "transcript_segments",
        sa.Column("evidence_provider", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transcript_segments", "evidence_provider")
    op.drop_column("transcript_segments", "evidence_origin")
    op.drop_column("videos", "last_opened_at")
    op.drop_constraint(
        "ck_workspaces_learning_history_limit",
        "workspaces",
        type_="check",
    )
    op.drop_column("workspaces", "learning_history_limit")
