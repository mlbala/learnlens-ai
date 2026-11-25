"""Pin a Gemini lesson so history trim keeps it.

Revision ID: 20261123_0013
Revises: 20261122_0012
Create Date: 2026-11-23

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261123_0013"
down_revision: str | None = "20261122_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("videos", "pinned")
