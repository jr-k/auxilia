"""Snapshot tool server icons on conversation shares.

Revision ID: d0a2c4e6f8b1
Revises: c9f1a3e5b7d2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "d0a2c4e6f8b1"
down_revision: str | Sequence[str] | None = "c9f1a3e5b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_shares",
        sa.Column("tool_servers", postgresql.JSONB(), nullable=True),
    )
    op.execute("UPDATE conversation_shares SET tool_servers = '[]'::jsonb")
    op.alter_column("conversation_shares", "tool_servers", nullable=False)


def downgrade() -> None:
    op.drop_column("conversation_shares", "tool_servers")
