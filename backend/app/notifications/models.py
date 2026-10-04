from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from app.models import BaseDBModel


class SlackNotificationSettingsDB(BaseDBModel, table=True):
    __tablename__ = "slack_notification_settings"
    __table_args__ = (
        CheckConstraint(
            "(bot_token_encrypted IS NULL) = (signing_secret_encrypted IS NULL)",
            name="ck_slack_notification_credentials_pair",
        ),
        UniqueConstraint(
            "workspace_id", "key", name="uq_slack_notifications_workspace_key"
        ),
    )

    workspace_id: UUID = Field(foreign_key="workspaces.id", index=True)
    slack_team_id: str | None = Field(default=None, unique=True, index=True)
    key: str = Field(default="default", nullable=False)
    enabled: bool = Field(default=False, nullable=False)
    bot_token_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    signing_secret_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


class TelegramNotificationSettingsDB(BaseDBModel, table=True):
    __tablename__ = "telegram_notification_settings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "key", name="uq_telegram_notifications_workspace_key"
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", index=True
    )
    key: str = Field(default="default", nullable=False)
    enabled: bool = Field(default=False, nullable=False)
    bot_id: str | None = Field(default=None, unique=True, index=True)
    bot_username: str | None = Field(default=None)
    bot_token_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    webhook_secret_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


class DiscordNotificationSettingsDB(BaseDBModel, table=True):
    __tablename__ = "discord_notification_settings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "key", name="uq_discord_notifications_workspace_key"
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", index=True
    )
    key: str = Field(default="default", nullable=False)
    enabled: bool = Field(default=False, nullable=False)
    application_id: str | None = Field(default=None, unique=True, index=True)
    bot_user_id: str | None = Field(default=None)
    bot_username: str | None = Field(default=None)
    public_key: str | None = Field(default=None)
    bot_token_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


class ExternalProvider(str, Enum):
    telegram = "telegram"
    discord = "discord"


class ExternalIdentityDB(BaseDBModel, table=True):
    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider",
            "external_user_id",
            name="uq_external_identity_provider_user",
        ),
        UniqueConstraint(
            "workspace_id",
            "provider",
            "user_id",
            name="uq_external_identity_internal_user",
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", index=True
    )
    provider: ExternalProvider = Field(
        sa_column=Column(
            SAEnum(ExternalProvider, native_enum=False, create_constraint=False),
            nullable=False,
        )
    )
    external_user_id: str = Field(index=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    display_name: str | None = Field(default=None)


class ExternalConversationDB(BaseDBModel, table=True):
    __tablename__ = "external_conversations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider",
            "external_chat_id",
            "external_thread_id",
            "external_user_id",
            name="uq_external_conversation_scope",
        ),
        UniqueConstraint("thread_id", name="uq_external_conversation_thread"),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", index=True
    )
    provider: ExternalProvider = Field(
        sa_column=Column(
            SAEnum(ExternalProvider, native_enum=False, create_constraint=False),
            nullable=False,
        )
    )
    external_chat_id: str = Field(index=True)
    # Empty string means the provider has no nested topic/thread.
    external_thread_id: str = Field(default="", nullable=False)
    external_user_id: str = Field(index=True)
    thread_id: str = Field(
        foreign_key="threads.id", ondelete="CASCADE", nullable=False, index=True
    )


class ExternalActionDB(BaseDBModel, table=True):
    __tablename__ = "external_actions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "token",
            name="uq_external_action_provider_token",
        ),
    )

    provider: ExternalProvider = Field(
        sa_column=Column(
            SAEnum(ExternalProvider, native_enum=False, create_constraint=False),
            nullable=False,
        )
    )
    token: str = Field(
        default_factory=lambda: uuid4().hex,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", index=True
    )
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    thread_id: str = Field(
        foreign_key="threads.id", ondelete="CASCADE", nullable=False, index=True
    )
    interrupt_id: str = Field(nullable=False)
    tool_call_id: str = Field(nullable=False)
    decision: str | None = Field(default=None)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
