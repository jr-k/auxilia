from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
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


class TelegramToolDiscoveryMode(str, Enum):
    """How a Telegram connection initializes a conversation's tool mode.

    After creation, the thread owns its mode so changes made from the
    corresponding web conversation also apply to Telegram.
    """

    disabled = "disabled"
    lazy = "lazy"
    local = "local"
    all_capabilities = "all_capabilities"

    @property
    def thread_mode(self) -> ThreadToolMode:
        return {
            TelegramToolDiscoveryMode.disabled: ThreadToolMode.eager,
            TelegramToolDiscoveryMode.lazy: ThreadToolMode.lazy,
            TelegramToolDiscoveryMode.local: ThreadToolMode.precision,
            TelegramToolDiscoveryMode.all_capabilities: ThreadToolMode.force_all,
        }[self]

    @property
    def force_enable_all_capabilities(self) -> bool:
        return self in {
            TelegramToolDiscoveryMode.lazy,
            TelegramToolDiscoveryMode.all_capabilities,
        }

    @property
    def runtime_mode(self) -> ToolDiscoveryMode:
        if self is TelegramToolDiscoveryMode.all_capabilities:
            return ToolDiscoveryMode.disabled
        return ToolDiscoveryMode(self.value)


class TelegramUpdateStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TelegramWorkspaceSettingsDB(BaseDBModel, table=True):
    __tablename__ = "telegram_workspace_settings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", name="uq_telegram_workspace_settings_workspace"
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )


class AgentTelegramBotDB(BaseDBModel, table=True):
    """One Telegram bot dedicated to one agent."""

    __tablename__ = "agent_telegram_bots"

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    agent_id: UUID = Field(
        foreign_key="agents.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    require_mention_in_groups: bool = Field(
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
    tool_discovery_mode: TelegramToolDiscoveryMode = Field(
        default=TelegramToolDiscoveryMode.lazy,
        sa_column=Column(
            SAEnum(
                TelegramToolDiscoveryMode,
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
            server_default=TelegramToolDiscoveryMode.lazy.value,
        ),
    )
    bot_id: str = Field(
        sa_column=Column(String(64), nullable=False, unique=True, index=True)
    )
    bot_username: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    bot_name: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    bot_token_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    webhook_secret_encrypted: str = Field(sa_column=Column(Text, nullable=False))


class TelegramIdentityDB(BaseDBModel, table=True):
    __tablename__ = "telegram_identities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "telegram_user_id",
            name="uq_telegram_identity_external",
        ),
        UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_telegram_identity_internal",
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    telegram_user_id: str = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    user_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )
    username: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    display_name: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )


class TelegramThreadBindingDB(BaseDBModel, table=True):
    __tablename__ = "telegram_thread_bindings"
    __table_args__ = (
        UniqueConstraint(
            "telegram_bot_id",
            "chat_id",
            "message_thread_id",
            "telegram_user_id",
            name="uq_telegram_thread_external",
        ),
        UniqueConstraint("thread_id", name="uq_telegram_thread_internal"),
    )

    telegram_bot_id: UUID = Field(
        foreign_key="agent_telegram_bots.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    thread_id: str = Field(
        foreign_key="threads.id", ondelete="CASCADE", nullable=False, index=True
    )
    chat_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    message_thread_id: str = Field(
        default="", sa_column=Column(String(64), nullable=False)
    )
    telegram_user_id: str = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    last_context_message_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )


class TelegramApprovalActionDB(BaseDBModel, table=True):
    __tablename__ = "telegram_approval_actions"
    __table_args__ = (
        UniqueConstraint("token", name="uq_telegram_approval_token"),
        UniqueConstraint(
            "thread_id",
            "interrupt_id",
            "tool_call_id",
            name="uq_telegram_approval_request",
        ),
    )

    token: str = Field(
        default_factory=lambda: uuid4().hex,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    telegram_bot_id: UUID = Field(
        foreign_key="agent_telegram_bots.id",
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
    message_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )


class TelegramUpdateDB(BaseDBModel, table=True):
    __tablename__ = "telegram_updates"
    __table_args__ = (
        UniqueConstraint("telegram_bot_id", "update_id", name="uq_telegram_update"),
    )

    telegram_bot_id: UUID = Field(
        foreign_key="agent_telegram_bots.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    update_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    payload: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    )
    status: TelegramUpdateStatus = Field(
        default=TelegramUpdateStatus.pending,
        sa_column=Column(
            SAEnum(
                TelegramUpdateStatus,
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
            server_default=TelegramUpdateStatus.pending.value,
        ),
    )
    attempts: int = Field(default=0, nullable=False)
    last_error: str | None = Field(
        default=None, sa_column=Column(String(128), nullable=True)
    )


class TelegramDeliveryCursorDB(BaseDBModel, table=True):
    __tablename__ = "telegram_delivery_cursors"
    __table_args__ = (UniqueConstraint("run_id", name="uq_telegram_delivery_run"),)

    run_id: str = Field(
        foreign_key="runs.id", ondelete="CASCADE", nullable=False, index=True
    )
    telegram_bot_id: UUID = Field(
        foreign_key="agent_telegram_bots.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    primary_message_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    extra_message_ids: list[int] = Field(
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


class TelegramContextMessageDB(BaseDBModel, table=True):
    __tablename__ = "telegram_context_messages"
    __table_args__ = (
        UniqueConstraint(
            "telegram_bot_id",
            "chat_id",
            "message_id",
            name="uq_telegram_context_message",
        ),
        Index(
            "ix_telegram_context_scope",
            "telegram_bot_id",
            "chat_id",
            "message_thread_id",
            "message_id",
        ),
        Index("ix_telegram_context_expiry", "expires_at"),
    )

    telegram_bot_id: UUID = Field(
        foreign_key="agent_telegram_bots.id",
        ondelete="CASCADE",
        nullable=False,
    )
    chat_id: str = Field(sa_column=Column(String(64), nullable=False))
    message_thread_id: str = Field(
        default="", sa_column=Column(String(64), nullable=False)
    )
    message_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    telegram_user_id: str | None = Field(
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
