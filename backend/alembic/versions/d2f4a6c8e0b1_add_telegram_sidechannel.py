"""add Telegram side-channel

Revision ID: d2f4a6c8e0b1
Revises: c1e3f5a7b9d2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "d2f4a6c8e0b1"
down_revision: str | Sequence[str] | None = "c1e3f5a7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), nullable=False),
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
    ]


def upgrade() -> None:
    op.create_table(
        "telegram_workspace_settings",
        *_base_columns(),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", name="uq_telegram_workspace_settings_workspace"
        ),
    )
    op.create_index(
        "ix_telegram_workspace_settings_workspace_id",
        "telegram_workspace_settings",
        ["workspace_id"],
    )

    op.create_table(
        "agent_telegram_bots",
        *_base_columns(),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "require_mention_in_groups",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "show_tool_callouts",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "tool_discovery_mode",
            sa.String(length=24),
            server_default="all_capabilities",
            nullable=False,
        ),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("bot_username", sa.String(length=255), nullable=True),
        sa.Column("bot_name", sa.String(length=255), nullable=True),
        sa.Column("bot_token_encrypted", sa.Text(), nullable=False),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_telegram_bots_workspace_id",
        "agent_telegram_bots",
        ["workspace_id"],
    )
    op.create_index(
        "ix_agent_telegram_bots_agent_id",
        "agent_telegram_bots",
        ["agent_id"],
    )
    op.create_index(
        "ix_agent_telegram_bots_bot_id",
        "agent_telegram_bots",
        ["bot_id"],
        unique=True,
    )
    op.create_table(
        "telegram_identities",
        *_base_columns(),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "telegram_user_id",
            name="uq_telegram_identity_external",
        ),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name="uq_telegram_identity_internal"
        ),
    )
    op.create_index(
        "ix_telegram_identities_workspace_id",
        "telegram_identities",
        ["workspace_id"],
    )
    op.create_index(
        "ix_telegram_identities_telegram_user_id",
        "telegram_identities",
        ["telegram_user_id"],
    )
    op.create_index(
        "ix_telegram_identities_user_id", "telegram_identities", ["user_id"]
    )

    op.create_table(
        "telegram_thread_bindings",
        *_base_columns(),
        sa.Column("telegram_bot_id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column(
            "message_thread_id",
            sa.String(length=64),
            server_default="",
            nullable=False,
        ),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("last_context_message_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["telegram_bot_id"], ["agent_telegram_bots.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "telegram_bot_id",
            "chat_id",
            "message_thread_id",
            "telegram_user_id",
            name="uq_telegram_thread_external",
        ),
        sa.UniqueConstraint("thread_id", name="uq_telegram_thread_internal"),
    )
    op.create_index(
        "ix_telegram_thread_bindings_telegram_bot_id",
        "telegram_thread_bindings",
        ["telegram_bot_id"],
    )
    op.create_index(
        "ix_telegram_thread_bindings_thread_id",
        "telegram_thread_bindings",
        ["thread_id"],
    )
    op.create_index(
        "ix_telegram_thread_bindings_chat_id",
        "telegram_thread_bindings",
        ["chat_id"],
    )
    op.create_index(
        "ix_telegram_thread_bindings_telegram_user_id",
        "telegram_thread_bindings",
        ["telegram_user_id"],
    )

    op.create_table(
        "telegram_approval_actions",
        *_base_columns(),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("telegram_bot_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("interrupt_id", sa.String(length=255), nullable=False),
        sa.Column("tool_call_id", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["telegram_bot_id"], ["agent_telegram_bots.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_telegram_approval_token"),
        sa.UniqueConstraint(
            "thread_id",
            "interrupt_id",
            "tool_call_id",
            name="uq_telegram_approval_request",
        ),
    )
    op.create_index(
        "ix_telegram_approval_actions_token",
        "telegram_approval_actions",
        ["token"],
    )
    op.create_index(
        "ix_telegram_approval_actions_telegram_bot_id",
        "telegram_approval_actions",
        ["telegram_bot_id"],
    )
    op.create_index(
        "ix_telegram_approval_actions_workspace_id",
        "telegram_approval_actions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_telegram_approval_actions_thread_id",
        "telegram_approval_actions",
        ["thread_id"],
    )

    op.create_table(
        "telegram_updates",
        *_base_columns(),
        sa.Column("telegram_bot_id", sa.UUID(), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=16), server_default="pending", nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["telegram_bot_id"], ["agent_telegram_bots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "telegram_bot_id", "update_id", name="uq_telegram_update"
        ),
    )
    op.create_index(
        "ix_telegram_updates_telegram_bot_id",
        "telegram_updates",
        ["telegram_bot_id"],
    )

    op.create_table(
        "telegram_delivery_cursors",
        *_base_columns(),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("telegram_bot_id", sa.UUID(), nullable=False),
        sa.Column("primary_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "extra_message_ids",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "sent_artifact_ids",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("completed", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["telegram_bot_id"], ["agent_telegram_bots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_telegram_delivery_run"),
    )
    op.create_index(
        "ix_telegram_delivery_cursors_run_id",
        "telegram_delivery_cursors",
        ["run_id"],
    )
    op.create_index(
        "ix_telegram_delivery_cursors_telegram_bot_id",
        "telegram_delivery_cursors",
        ["telegram_bot_id"],
    )

    op.create_table(
        "telegram_context_messages",
        *_base_columns(),
        sa.Column("telegram_bot_id", sa.UUID(), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column(
            "message_thread_id",
            sa.String(length=64),
            server_default="",
            nullable=False,
        ),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["telegram_bot_id"], ["agent_telegram_bots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "telegram_bot_id",
            "chat_id",
            "message_id",
            name="uq_telegram_context_message",
        ),
    )
    op.create_index(
        "ix_telegram_context_scope",
        "telegram_context_messages",
        ["telegram_bot_id", "chat_id", "message_thread_id", "message_id"],
    )
    op.create_index(
        "ix_telegram_context_expiry",
        "telegram_context_messages",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_table("telegram_context_messages")
    op.execute("DROP TABLE IF EXISTS telegram_delivery_cursors")
    op.drop_table("telegram_updates")
    op.drop_table("telegram_approval_actions")
    op.drop_table("telegram_thread_bindings")
    op.drop_table("telegram_identities")
    op.drop_table("agent_telegram_bots")
    op.drop_table("telegram_workspace_settings")
