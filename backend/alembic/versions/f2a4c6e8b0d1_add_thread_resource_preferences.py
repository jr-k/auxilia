"""add thread resource preferences

Revision ID: f2a4c6e8b0d1
Revises: e1f3a5c7b9d2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "f2a4c6e8b0d1"
down_revision: str | Sequence[str] | None = "e1f3a5c7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "threads",
        sa.Column(
            "disabled_mcp_server_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "threads",
        sa.Column(
            "disabled_skill_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("threads", "disabled_skill_ids")
    op.drop_column("threads", "disabled_mcp_server_ids")
