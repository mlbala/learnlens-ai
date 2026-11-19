"""Add result_resource_id to ingestion_jobs for import Idempotency-Key replay.

Revision ID: 20261119_0002
Revises: 20261118_0001
Create Date: 2026-11-19

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261119_0002"
down_revision: str | None = "20261118_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("result_resource_id", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "result_resource_id")
