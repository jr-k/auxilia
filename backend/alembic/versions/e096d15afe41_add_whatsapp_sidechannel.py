"""add WhatsApp sidechannel

Revision ID: e096d15afe41
Revises: i7e9a1c3f5b8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "e096d15afe41"
down_revision: str | Sequence[str] | None = "i7e9a1c3f5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_columns() -> list[sa.Column]:
    return [
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
        sa.Column("id", sa.UUID(), nullable=False),
    ]


def _json_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
        server_default=sa.text("'[]'"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "whatsapp_identities",
        *_base_columns(),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("whatsapp_user_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("phone_number", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name="uq_whatsapp_identity_internal"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "whatsapp_user_id",
            name="uq_whatsapp_identity_external",
        ),
    )
    op.create_index(
        "ix_whatsapp_identities_user_id", "whatsapp_identities", ["user_id"]
    )
    op.create_index(
        "ix_whatsapp_identities_whatsapp_user_id",
        "whatsapp_identities",
        ["whatsapp_user_id"],
    )
    op.create_index(
        "ix_whatsapp_identities_workspace_id",
        "whatsapp_identities",
        ["workspace_id"],
    )

    op.create_table(
        "whatsapp_workspace_settings",
        *_base_columns(),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", name="uq_whatsapp_workspace_settings_workspace"
        ),
    )
    op.create_index(
        "ix_whatsapp_workspace_settings_workspace_id",
        "whatsapp_workspace_settings",
        ["workspace_id"],
    )

    op.create_table(
        "agent_whatsapp_connections",
        *_base_columns(),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "show_typing_indicator",
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
            "show_auxilia_link",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "tool_discovery_mode",
            sa.String(length=24),
            server_default="lazy",
            nullable=False,
        ),
        sa.Column("business_account_id", sa.String(length=64), nullable=False),
        sa.Column("phone_number_id", sa.String(length=64), nullable=False),
        sa.Column("display_phone_number", sa.String(length=64), nullable=True),
        sa.Column("verified_name", sa.String(length=255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("app_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("verify_token_encrypted", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_whatsapp_connections_agent_id",
        "agent_whatsapp_connections",
        ["agent_id"],
    )
    op.create_index(
        "ix_agent_whatsapp_connections_business_account_id",
        "agent_whatsapp_connections",
        ["business_account_id"],
    )
    op.create_index(
        "ix_agent_whatsapp_connections_phone_number_id",
        "agent_whatsapp_connections",
        ["phone_number_id"],
        unique=True,
    )
    op.create_index(
        "ix_agent_whatsapp_connections_workspace_id",
        "agent_whatsapp_connections",
        ["workspace_id"],
    )

    op.create_table(
        "whatsapp_context_messages",
        *_base_columns(),
        sa.Column("whatsapp_connection_id", sa.UUID(), nullable=False),
        sa.Column("chat_id", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("whatsapp_user_id", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["whatsapp_connection_id"],
            ["agent_whatsapp_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "whatsapp_connection_id",
            "message_id",
            name="uq_whatsapp_context_message",
        ),
    )
    op.create_index(
        "ix_whatsapp_context_expiry",
        "whatsapp_context_messages",
        ["expires_at"],
    )
    op.create_index(
        "ix_whatsapp_context_scope",
        "whatsapp_context_messages",
        ["whatsapp_connection_id", "chat_id", "sent_at"],
    )

    op.create_table(
        "whatsapp_sessions",
        *_base_columns(),
        sa.Column("whatsapp_connection_id", sa.UUID(), nullable=False),
        sa.Column("recipient_type", sa.String(length=16), nullable=False),
        sa.Column("recipient_id", sa.String(length=128), nullable=False),
        sa.Column("last_user_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["whatsapp_connection_id"],
            ["agent_whatsapp_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "whatsapp_connection_id",
            "recipient_type",
            "recipient_id",
            name="uq_whatsapp_session_recipient",
        ),
    )
    op.create_index(
        "ix_whatsapp_sessions_recipient_id", "whatsapp_sessions", ["recipient_id"]
    )
    op.create_index(
        "ix_whatsapp_sessions_whatsapp_connection_id",
        "whatsapp_sessions",
        ["whatsapp_connection_id"],
    )

    op.create_table(
        "whatsapp_webhook_events",
        *_base_columns(),
        sa.Column("whatsapp_connection_id", sa.UUID(), nullable=False),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["whatsapp_connection_id"],
            ["agent_whatsapp_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "whatsapp_connection_id",
            "event_key",
            name="uq_whatsapp_webhook_event",
        ),
    )
    op.create_index(
        "ix_whatsapp_webhook_events_whatsapp_connection_id",
        "whatsapp_webhook_events",
        ["whatsapp_connection_id"],
    )

    op.create_table(
        "whatsapp_outbound_messages",
        *_base_columns(),
        sa.Column("whatsapp_connection_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("recipient_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["whatsapp_connection_id"],
            ["agent_whatsapp_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "whatsapp_connection_id",
            "message_id",
            name="uq_whatsapp_outbound_message",
        ),
    )
    op.create_index(
        "ix_whatsapp_outbound_messages_whatsapp_connection_id",
        "whatsapp_outbound_messages",
        ["whatsapp_connection_id"],
    )
    op.create_index(
        "ix_whatsapp_outbound_messages_message_id",
        "whatsapp_outbound_messages",
        ["message_id"],
    )

    op.create_table(
        "whatsapp_approval_actions",
        *_base_columns(),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("whatsapp_connection_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("interrupt_id", sa.String(length=255), nullable=False),
        sa.Column("tool_call_id", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["whatsapp_connection_id"],
            ["agent_whatsapp_connections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "thread_id",
            "interrupt_id",
            "tool_call_id",
            name="uq_whatsapp_approval_request",
        ),
        sa.UniqueConstraint("token", name="uq_whatsapp_approval_token"),
    )
    op.create_index(
        "ix_whatsapp_approval_actions_thread_id",
        "whatsapp_approval_actions",
        ["thread_id"],
    )
    op.create_index(
        "ix_whatsapp_approval_actions_token",
        "whatsapp_approval_actions",
        ["token"],
    )
    op.create_index(
        "ix_whatsapp_approval_actions_whatsapp_connection_id",
        "whatsapp_approval_actions",
        ["whatsapp_connection_id"],
    )
    op.create_index(
        "ix_whatsapp_approval_actions_workspace_id",
        "whatsapp_approval_actions",
        ["workspace_id"],
    )

    op.create_table(
        "whatsapp_thread_bindings",
        *_base_columns(),
        sa.Column("whatsapp_connection_id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.String(length=128), nullable=False),
        sa.Column("whatsapp_user_id", sa.String(length=64), nullable=False),
        sa.Column("last_context_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["whatsapp_connection_id"],
            ["agent_whatsapp_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", name="uq_whatsapp_thread_internal"),
        sa.UniqueConstraint(
            "whatsapp_connection_id",
            "chat_id",
            "whatsapp_user_id",
            name="uq_whatsapp_thread_external",
        ),
    )
    for column in (
        "chat_id",
        "thread_id",
        "whatsapp_connection_id",
        "whatsapp_user_id",
    ):
        op.create_index(
            f"ix_whatsapp_thread_bindings_{column}",
            "whatsapp_thread_bindings",
            [column],
        )

    op.create_table(
        "whatsapp_delivery_cursors",
        *_base_columns(),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("whatsapp_connection_id", sa.UUID(), nullable=False),
        _json_column("sent_message_ids"),
        _json_column("sent_artifact_ids"),
        sa.Column("completed", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["whatsapp_connection_id"],
            ["agent_whatsapp_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_whatsapp_delivery_run"),
    )
    op.create_index(
        "ix_whatsapp_delivery_cursors_run_id",
        "whatsapp_delivery_cursors",
        ["run_id"],
    )
    op.create_index(
        "ix_whatsapp_delivery_cursors_whatsapp_connection_id",
        "whatsapp_delivery_cursors",
        ["whatsapp_connection_id"],
    )


def downgrade() -> None:
    op.drop_table("whatsapp_delivery_cursors")
    op.drop_table("whatsapp_thread_bindings")
    op.drop_table("whatsapp_approval_actions")
    op.drop_table("whatsapp_outbound_messages")
    op.drop_table("whatsapp_webhook_events")
    op.drop_table("whatsapp_sessions")
    op.drop_table("whatsapp_context_messages")
    op.drop_table("agent_whatsapp_connections")
    op.drop_table("whatsapp_workspace_settings")
    op.drop_table("whatsapp_identities")
