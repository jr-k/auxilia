from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.agents.models import ToolDiscoveryMode
from app.models import BaseDBModel
from app.threads.models import ThreadToolMode


class WhatsAppToolDiscoveryMode(str, Enum):
    disabled = "disabled"
    lazy = "lazy"
    local = "local"
    all_capabilities = "all_capabilities"

    @property
    def thread_mode(self) -> ThreadToolMode:
        return {
            WhatsAppToolDiscoveryMode.disabled: ThreadToolMode.eager,
            WhatsAppToolDiscoveryMode.lazy: ThreadToolMode.lazy,
            WhatsAppToolDiscoveryMode.local: ThreadToolMode.precision,
            WhatsAppToolDiscoveryMode.all_capabilities: ThreadToolMode.force_all,
        }[self]

    @property
    def force_enable_all_capabilities(self) -> bool:
        return self in {
            WhatsAppToolDiscoveryMode.lazy,
            WhatsAppToolDiscoveryMode.all_capabilities,
        }

    @property
    def runtime_mode(self) -> ToolDiscoveryMode:
        if self is WhatsAppToolDiscoveryMode.all_capabilities:
            return ToolDiscoveryMode.disabled
        return ToolDiscoveryMode(self.value)


class WhatsAppUpdateStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class WhatsAppWorkspaceSettingsDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_workspace_settings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", name="uq_whatsapp_workspace_settings_workspace"
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )


class AgentWhatsAppConnectionDB(BaseDBModel, table=True):
    __tablename__ = "agent_whatsapp_connections"

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    agent_id: UUID = Field(
        foreign_key="agents.id", ondelete="CASCADE", nullable=False, index=True
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    show_typing_indicator: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    show_tool_callouts: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    show_auxilia_link: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    tool_discovery_mode: WhatsAppToolDiscoveryMode = Field(
        default=WhatsAppToolDiscoveryMode.lazy,
        sa_column=Column(
            SAEnum(
                WhatsAppToolDiscoveryMode,
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
            server_default=WhatsAppToolDiscoveryMode.lazy.value,
        ),
    )
    business_account_id: str = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    phone_number_id: str = Field(
        sa_column=Column(String(64), nullable=False, unique=True, index=True)
    )
    display_phone_number: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    verified_name: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    access_token_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    app_secret_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    verify_token_encrypted: str = Field(sa_column=Column(Text, nullable=False))


class WhatsAppIdentityDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_identities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "whatsapp_user_id", name="uq_whatsapp_identity_external"
        ),
        UniqueConstraint(
            "workspace_id", "user_id", name="uq_whatsapp_identity_internal"
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    whatsapp_user_id: str = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    user_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )
    phone_number: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    display_name: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )


class WhatsAppSessionDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_sessions"
    __table_args__ = (
        UniqueConstraint(
            "whatsapp_connection_id",
            "recipient_type",
            "recipient_id",
            name="uq_whatsapp_session_recipient",
        ),
    )

    whatsapp_connection_id: UUID = Field(
        foreign_key="agent_whatsapp_connections.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    recipient_type: str = Field(
        default="individual", sa_column=Column(String(16), nullable=False)
    )
    recipient_id: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    last_user_message_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class WhatsAppThreadBindingDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_thread_bindings"
    __table_args__ = (
        UniqueConstraint(
            "whatsapp_connection_id",
            "chat_id",
            "whatsapp_user_id",
            name="uq_whatsapp_thread_external",
        ),
        UniqueConstraint("thread_id", name="uq_whatsapp_thread_internal"),
    )

    whatsapp_connection_id: UUID = Field(
        foreign_key="agent_whatsapp_connections.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    thread_id: str = Field(
        foreign_key="threads.id", ondelete="CASCADE", nullable=False, index=True
    )
    chat_id: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    whatsapp_user_id: str = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    last_context_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class WhatsAppApprovalActionDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_approval_actions"
    __table_args__ = (
        UniqueConstraint("token", name="uq_whatsapp_approval_token"),
        UniqueConstraint(
            "thread_id",
            "interrupt_id",
            "tool_call_id",
            name="uq_whatsapp_approval_request",
        ),
    )

    token: str = Field(
        default_factory=lambda: uuid4().hex,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    whatsapp_connection_id: UUID = Field(
        foreign_key="agent_whatsapp_connections.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", nullable=False)
    thread_id: str = Field(
        foreign_key="threads.id", ondelete="CASCADE", nullable=False, index=True
    )
    interrupt_id: str = Field(sa_column=Column(String(255), nullable=False))
    tool_call_id: str = Field(sa_column=Column(String(255), nullable=False))
    decision: str | None = Field(
        default=None, sa_column=Column(String(16), nullable=True)
    )
    message_id: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )


class WhatsAppWebhookEventDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "whatsapp_connection_id",
            "event_key",
            name="uq_whatsapp_webhook_event",
        ),
    )

    whatsapp_connection_id: UUID = Field(
        foreign_key="agent_whatsapp_connections.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    event_key: str = Field(sa_column=Column(String(64), nullable=False))
    payload: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    )
    status: WhatsAppUpdateStatus = Field(
        default=WhatsAppUpdateStatus.pending,
        sa_column=Column(
            SAEnum(
                WhatsAppUpdateStatus,
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
            server_default=WhatsAppUpdateStatus.pending.value,
        ),
    )
    attempts: int = Field(default=0, nullable=False)
    last_error: str | None = Field(
        default=None, sa_column=Column(String(128), nullable=True)
    )


class WhatsAppOutboundMessageDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_outbound_messages"
    __table_args__ = (
        UniqueConstraint(
            "whatsapp_connection_id",
            "message_id",
            name="uq_whatsapp_outbound_message",
        ),
    )

    whatsapp_connection_id: UUID = Field(
        foreign_key="agent_whatsapp_connections.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    message_id: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    recipient_id: str = Field(sa_column=Column(String(128), nullable=False))
    status: str = Field(
        default="accepted", sa_column=Column(String(16), nullable=False)
    )
    status_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class WhatsAppDeliveryCursorDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_delivery_cursors"
    __table_args__ = (UniqueConstraint("run_id", name="uq_whatsapp_delivery_run"),)

    run_id: str = Field(
        foreign_key="runs.id", ondelete="CASCADE", nullable=False, index=True
    )
    whatsapp_connection_id: UUID = Field(
        foreign_key="agent_whatsapp_connections.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    sent_message_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            JSON().with_variant(JSONB(), "postgresql"),
            nullable=False,
            server_default=text("'[]'"),
        ),
    )
    sent_artifact_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            JSON().with_variant(JSONB(), "postgresql"),
            nullable=False,
            server_default=text("'[]'"),
        ),
    )
    completed: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )


class WhatsAppContextMessageDB(BaseDBModel, table=True):
    __tablename__ = "whatsapp_context_messages"
    __table_args__ = (
        UniqueConstraint(
            "whatsapp_connection_id",
            "message_id",
            name="uq_whatsapp_context_message",
        ),
        Index(
            "ix_whatsapp_context_scope",
            "whatsapp_connection_id",
            "chat_id",
            "sent_at",
        ),
        Index("ix_whatsapp_context_expiry", "expires_at"),
    )

    whatsapp_connection_id: UUID = Field(
        foreign_key="agent_whatsapp_connections.id",
        ondelete="CASCADE",
        nullable=False,
    )
    chat_id: str = Field(sa_column=Column(String(128), nullable=False))
    message_id: str = Field(sa_column=Column(String(255), nullable=False))
    whatsapp_user_id: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    display_name: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    sent_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
