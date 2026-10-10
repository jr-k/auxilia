"""add Slack thread context cursor

Revision ID: b3e7c1d9a5f2
Revises: f2a4c6e8b0d1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "b3e7c1d9a5f2"
down_revision: str | Sequence[str] | None = "f2a4c6e8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "slack_thread_bindings",
        sa.Column("last_context_ts", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("slack_thread_bindings", "last_context_ts")
