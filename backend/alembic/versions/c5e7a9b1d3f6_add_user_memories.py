"""Add global user memories and per-thread activation.

Revision ID: c5e7a9b1d3f6
Revises: b4d6f8a0c2e3
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "c5e7a9b1d3f6"
down_revision: str | Sequence[str] | None = "b4d6f8a0c2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "normalized_name",
            name="uq_memory_categories_user_name",
        ),
    )
    op.create_index(
        "ix_memory_categories_user_id",
        "memory_categories",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_memory_categories_user_position",
        "memory_categories",
        ["user_id", "position"],
        unique=False,
    )

    op.create_table(
        "memory_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "auto_capture_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_memory_preferences_user_id"),
    )
    op.create_index(
        "ix_memory_preferences_user_id",
        "memory_preferences",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "memories",
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=16),
            server_default="manual",
            nullable=False,
        ),
        sa.Column("source_thread_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["memory_categories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_thread_id"],
            ["threads.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "category_id",
            "key",
            name="uq_memories_category_key",
        ),
    )
    op.create_index(
        "ix_memories_category_id",
        "memories",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        "ix_memories_source_thread_id",
        "memories",
        ["source_thread_id"],
        unique=False,
    )
    op.create_index(
        "ix_memories_user_id",
        "memories",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_memories_user_updated",
        "memories",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.add_column(
        "threads",
        sa.Column(
            "memories_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("threads", "memories_enabled")
    op.drop_index("ix_memories_user_updated", table_name="memories")
    op.drop_index("ix_memories_user_id", table_name="memories")
    op.drop_index("ix_memories_source_thread_id", table_name="memories")
    op.drop_index("ix_memories_category_id", table_name="memories")
    op.drop_table("memories")
    op.drop_index(
        "ix_memory_preferences_user_id",
        table_name="memory_preferences",
    )
    op.drop_table("memory_preferences")
    op.drop_index(
        "ix_memory_categories_user_position",
        table_name="memory_categories",
    )
    op.drop_index(
        "ix_memory_categories_user_id",
        table_name="memory_categories",
    )
    op.drop_table("memory_categories")
