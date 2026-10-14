"""add thread subagent preferences

Revision ID: b5f7d9a1c3e4
Revises: a4e6c8f0b2d3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "b5f7d9a1c3e4"
down_revision: str | Sequence[str] | None = "a4e6c8f0b2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "threads",
        sa.Column(
            "disabled_subagent_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("threads", "disabled_subagent_ids")
