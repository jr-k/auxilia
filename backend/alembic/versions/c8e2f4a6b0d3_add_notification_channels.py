"""add notification channels

Revision ID: c8e2f4a6b0d3
Revises: b7d1e3f5a9c2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "c8e2f4a6b0d3"
down_revision: str | Sequence[str] | None = "b7d1e3f5a9c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    created_at, updated_at = _timestamps()
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "config",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_channels_workspace_id",
        "notification_channels",
        ["workspace_id"],
    )
    op.create_index(
        "ix_notification_channels_user_id",
        "notification_channels",
        ["user_id"],
    )
    op.create_index(
        "ix_notification_channels_defaults",
        "notification_channels",
        ["workspace_id", "user_id", "is_default"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_notification_channels_user_name_ci "
        "ON notification_channels (workspace_id, user_id, lower(name))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_notification_channels_single_browser "
        "ON notification_channels (workspace_id, user_id) "
        "WHERE channel_type = 'browser'"
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "trigger_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trigger_id", sa.Uuid(), nullable=False),
        sa.Column(
            "channel_ids",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(["trigger_id"], ["triggers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trigger_id", name="uq_trigger_notifications_trigger"),
    )
    op.create_index(
        "ix_trigger_notifications_trigger_id",
        "trigger_notifications",
        ["trigger_id"],
    )

    op.add_column(
        "workspace_event_outbox",
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("workspace_event_outbox", "payload")
    op.drop_table("trigger_notifications")
    op.drop_table("notification_channels")
