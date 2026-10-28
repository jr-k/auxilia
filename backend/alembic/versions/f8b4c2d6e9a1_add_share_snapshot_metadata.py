"""Add metadata and run timing to conversation share snapshots.

Revision ID: f8b4c2d6e9a1
Revises: c5e7a9b1d3f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "f8b4c2d6e9a1"
down_revision: str | Sequence[str] | None = "c5e7a9b1d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_shares",
        sa.Column("model_id", sa.String(), nullable=True),
    )
    op.add_column(
        "conversation_shares",
        sa.Column("model_name", sa.String(), nullable=True),
    )
    op.add_column(
        "conversation_shares",
        sa.Column("memories_enabled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "conversation_shares",
        sa.Column("cost", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "conversation_shares",
        sa.Column(
            "runs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column("conversation_shares", "runs", server_default=None)


def downgrade() -> None:
    op.drop_column("conversation_shares", "runs")
    op.drop_column("conversation_shares", "cost")
    op.drop_column("conversation_shares", "memories_enabled")
    op.drop_column("conversation_shares", "model_name")
    op.drop_column("conversation_shares", "model_id")
