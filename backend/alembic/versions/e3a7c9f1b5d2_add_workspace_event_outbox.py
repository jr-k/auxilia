"""add workspace event outbox

Revision ID: e3a7c9f1b5d2
Revises: d2f6a8c0e4b1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e3a7c9f1b5d2"
down_revision: str | Sequence[str] | None = "d2f6a8c0e4b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_event_outbox",
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
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workspace_event_outbox_created_at",
        "workspace_event_outbox",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_event_outbox_target_user_id",
        "workspace_event_outbox",
        ["target_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_event_outbox_workspace_id",
        "workspace_event_outbox",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_event_outbox_workspace_id",
        table_name="workspace_event_outbox",
    )
    op.drop_index(
        "ix_workspace_event_outbox_target_user_id",
        table_name="workspace_event_outbox",
    )
    op.drop_index(
        "ix_workspace_event_outbox_created_at",
        table_name="workspace_event_outbox",
    )
    op.drop_table("workspace_event_outbox")
