"""add trigger tool preferences

Revision ID: e5f7a9b1c3d6
Revises: d4e6f8a0b2c5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "e5f7a9b1c3d6"
down_revision: str | Sequence[str] | None = "d4e6f8a0b2c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "triggers",
        sa.Column(
            "disabled_mcp_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "threads",
        sa.Column(
            "disabled_mcp_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("threads", "disabled_mcp_tools")
    op.drop_column("triggers", "disabled_mcp_tools")
