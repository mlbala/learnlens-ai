"""Add media_assets and media_frames for opt-in authorized media (phase 17).

Revision ID: 20261120_0008
Revises: 20261120_0007
Create Date: 2026-11-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261120_0008"
down_revision: str | None = "20261120_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("media_kind", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("rights_attested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "provider_transfer_consented_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column(
            "antivirus_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="queued"
        ),
        sa.Column("source_asset_id", sa.Uuid(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["source_asset_id"], ["source_assets.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_assets_workspace_id", "media_assets", ["workspace_id"])
    op.create_index("ix_media_assets_video_id", "media_assets", ["video_id"])

    op.create_table(
        "media_frames",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=True),
        sa.Column(
            "frame_kind", sa.String(length=32), nullable=False, server_default="frame"
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column(
            "alignment_confidence", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "provenance",
            sa.String(length=64),
            nullable=False,
            server_default="fixture_data",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "media_asset_id", "ordinal", name="uq_media_frames_asset_ordinal"
        ),
    )
    op.create_index("ix_media_frames_media_asset_id", "media_frames", ["media_asset_id"])
    op.create_index("ix_media_frames_workspace_id", "media_frames", ["workspace_id"])
    op.create_index("ix_media_frames_video_id", "media_frames", ["video_id"])


def downgrade() -> None:
    op.drop_index("ix_media_frames_video_id", table_name="media_frames")
    op.drop_index("ix_media_frames_workspace_id", table_name="media_frames")
    op.drop_index("ix_media_frames_media_asset_id", table_name="media_frames")
    op.drop_table("media_frames")
    op.drop_index("ix_media_assets_video_id", table_name="media_assets")
    op.drop_index("ix_media_assets_workspace_id", table_name="media_assets")
    op.drop_table("media_assets")
