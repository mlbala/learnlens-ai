"""Add usage_limits table for workspace quotas and cost tracking.

Revision ID: 20261120_0007
Revises: 20261120_0006
Create Date: 2026-11-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261120_0007"
down_revision: str | None = "20261120_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("jobs_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requests_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_spend_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("jobs_cap", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("tokens_cap", sa.Integer(), nullable=False, server_default="2000000"),
        sa.Column("requests_cap", sa.Integer(), nullable=False, server_default="10000"),
        sa.Column(
            "spend_cap_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="25",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_usage_limits_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_limits"),
        sa.UniqueConstraint(
            "workspace_id", "period", name="uq_usage_limits_workspace_period"
        ),
    )
    op.create_index("ix_usage_limits_workspace_id", "usage_limits", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_limits_workspace_id", table_name="usage_limits")
    op.drop_table("usage_limits")
