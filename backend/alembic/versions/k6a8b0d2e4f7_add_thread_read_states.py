"""add thread read states

Revision ID: k6a8b0d2e4f7
Revises: j5f7a9c1d3e6
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "k6a8b0d2e4f7"
down_revision: str | Sequence[str] | None = "j5f7a9c1d3e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "threads",
        sa.Column(
            "response_version",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_table(
        "thread_read_states",
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "last_read_version",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "manually_unread",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["threads.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("thread_id", "user_id"),
    )
    op.create_index(
        "ix_thread_read_states_user_id",
        "thread_read_states",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_thread_read_states_user_id",
        table_name="thread_read_states",
    )
    op.drop_table("thread_read_states")
    op.drop_column("threads", "response_version")
