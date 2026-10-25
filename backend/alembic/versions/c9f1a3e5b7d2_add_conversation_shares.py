"""Add revocable public conversation snapshots.

Revision ID: c9f1a3e5b7d2
Revises: b7e3d1f0a9c2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "c9f1a3e5b7d2"
down_revision: str | Sequence[str] | None = "b7e3d1f0a9c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_shares",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            sa.String(),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checkpoint_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("agent_emoji", sa.String(), nullable=True),
        sa.Column("agent_color", sa.String(), nullable=True),
        sa.UniqueConstraint(
            "workspace_id",
            "thread_id",
            name="uq_conversation_shares_workspace_thread",
        ),
    )
    op.create_index(
        "ix_conversation_shares_workspace_id",
        "conversation_shares",
        ["workspace_id"],
    )
    op.create_index(
        "ix_conversation_shares_thread_id",
        "conversation_shares",
        ["thread_id"],
    )
    op.create_table(
        "conversation_share_artifacts",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "share_id",
            sa.Uuid(),
            sa.ForeignKey("conversation_shares.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "artifact_id",
            sa.Uuid(),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("tool_call_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("conversation_share_artifacts")
    op.drop_index("ix_conversation_shares_thread_id", table_name="conversation_shares")
    op.drop_index(
        "ix_conversation_shares_workspace_id", table_name="conversation_shares"
    )
    op.drop_table("conversation_shares")
