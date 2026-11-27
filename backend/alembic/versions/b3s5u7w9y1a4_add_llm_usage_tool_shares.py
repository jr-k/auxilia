"""add per-MCP-server and per-skill shares of llm usage

Revision ID: b3s5u7w9y1a4
Revises: a2r4t6v8x0z3
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "b3s5u7w9y1a4"
down_revision: str | Sequence[str] | None = "a2r4t6v8x0z3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_tool_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usage_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=16), nullable=False),
        sa.Column("key", sa.Uuid(), nullable=True),
        sa.Column("weight", sa.Numeric(12, 10), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["usage_id"], ["llm_usage.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "usage_id",
            "dimension",
            "key",
            name="uq_llm_usage_tool_shares_usage_dimension_key",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.add_column(
        "llm_usage_state",
        sa.Column(
            "tool_shares_started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "llm_usage_state",
        sa.Column(
            "tool_shares_backfill_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("llm_usage_state", "tool_shares_backfill_completed_at")
    op.drop_column("llm_usage_state", "tool_shares_started_at")
    op.drop_table("llm_usage_tool_shares")
