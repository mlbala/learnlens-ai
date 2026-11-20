"""Add provider_runs and summaries tables for phase 06.

Revision ID: 20261120_0003
Revises: 20261119_0002
Create Date: 2026-11-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261120_0003"
down_revision: str | None = "20261119_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("token_in", sa.Integer(), nullable=True),
        sa.Column("token_out", sa.Integer(), nullable=True),
        sa.Column("cost_estimate_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_provider_runs_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_provider_runs"),
    )
    op.create_index("ix_provider_runs_workspace_id", "provider_runs", ["workspace_id"])
    op.create_index("ix_provider_runs_request_hash", "provider_runs", ["request_hash"])

    op.create_table(
        "summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("scope_kind", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("summary_kind", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("coverage_json", sa.JSON(), nullable=True),
        sa.Column("provider_run_id", sa.Uuid(), nullable=True),
        sa.Column("cache_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_run_id"],
            ["provider_runs.id"],
            name="fk_summaries_provider_run_id_provider_runs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_summaries_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_summaries"),
        sa.UniqueConstraint(
            "workspace_id",
            "scope_kind",
            "scope_id",
            "summary_kind",
            "revision",
            name="uq_summaries_scope_kind_revision",
        ),
    )
    op.create_index("ix_summaries_workspace_id", "summaries", ["workspace_id"])
    op.create_index("ix_summaries_scope_id", "summaries", ["scope_id"])
    op.create_index("ix_summaries_cache_key", "summaries", ["cache_key"])


def downgrade() -> None:
    op.drop_index("ix_summaries_cache_key", table_name="summaries")
    op.drop_index("ix_summaries_scope_id", table_name="summaries")
    op.drop_index("ix_summaries_workspace_id", table_name="summaries")
    op.drop_table("summaries")
    op.drop_index("ix_provider_runs_request_hash", table_name="provider_runs")
    op.drop_index("ix_provider_runs_workspace_id", table_name="provider_runs")
    op.drop_table("provider_runs")
