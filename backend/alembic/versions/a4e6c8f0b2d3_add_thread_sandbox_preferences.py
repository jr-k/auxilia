"""add thread sandbox preferences

Revision ID: a4e6c8f0b2d3
Revises: f3c5d7e9a1b2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "a4e6c8f0b2d3"
down_revision: str | Sequence[str] | None = "f3c5d7e9a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "threads",
        sa.Column(
            "disabled_sandbox_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("threads", "disabled_sandbox_ids")
