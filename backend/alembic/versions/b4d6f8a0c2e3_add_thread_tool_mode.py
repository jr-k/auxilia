"""Add a conversation-level tool mode.

Revision ID: b4d6f8a0c2e3
Revises: a3b5c7d9e1f2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "b4d6f8a0c2e3"
down_revision: str | Sequence[str] | None = "a3b5c7d9e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "threads",
        sa.Column("tool_mode", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("threads", "tool_mode")
