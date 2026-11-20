"""Add index_manifests for phase 07 Qdrant hybrid retrieval.

Revision ID: 20261120_0004
Revises: 20261120_0003
Create Date: 2026-11-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261120_0004"
down_revision: str | None = "20261120_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "index_manifests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("embedding_profile", sa.String(length=200), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("qdrant_collection", sa.String(length=255), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("processing_version", sa.String(length=64), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("previous_collection", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name="fk_index_manifests_video_id_videos",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_index_manifests_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_index_manifests"),
        sa.UniqueConstraint(
            "workspace_id",
            "video_id",
            "embedding_profile",
            "source_revision",
            name="uq_index_manifests_video_profile_revision",
        ),
    )
    op.create_index(
        "ix_index_manifests_workspace_id",
        "index_manifests",
        ["workspace_id"],
    )
    op.create_index(
        "ix_index_manifests_video_id",
        "index_manifests",
        ["video_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_index_manifests_video_id", table_name="index_manifests")
    op.drop_index("ix_index_manifests_workspace_id", table_name="index_manifests")
    op.drop_table("index_manifests")
