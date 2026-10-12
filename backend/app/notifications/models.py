from enum import Enum
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Enum as SAEnum,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models import BaseDBModel


class NotificationChannelType(str, Enum):
    browser = "browser"
    slack = "slack"


class NotificationChannelDB(BaseDBModel, table=True):
    """A named destination owned by one workspace user."""

    __tablename__ = "notification_channels"
    __table_args__ = (
        Index(
            "uq_notification_channels_user_name_ci",
            "workspace_id",
            "user_id",
            text("lower(name)"),
            unique=True,
        ),
        Index(
            "uq_notification_channels_single_browser",
            "workspace_id",
            "user_id",
            unique=True,
            postgresql_where=text("channel_type = 'browser'"),
            sqlite_where=text("channel_type = 'browser'"),
        ),
        Index(
            "ix_notification_channels_defaults",
            "workspace_id",
            "user_id",
            "is_default",
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    user_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )
    name: str = Field(max_length=100, nullable=False)
    channel_type: NotificationChannelType = Field(
        sa_column=Column(
            SAEnum(
                NotificationChannelType,
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        )
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    is_default: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(
            JSON().with_variant(JSONB(), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
    )


class TriggerNotificationDB(BaseDBModel, table=True):
    """Marks a trigger whose completed run is delivered as a notification.

    An empty ``channel_ids`` list means "resolve the owner's enabled defaults
    when this occurrence finishes", so changing defaults updates every future
    firing without rewriting triggers.
    """

    __tablename__ = "trigger_notifications"
    __table_args__ = (
        UniqueConstraint("trigger_id", name="uq_trigger_notifications_trigger"),
    )

    trigger_id: UUID = Field(
        foreign_key="triggers.id", ondelete="CASCADE", nullable=False, index=True
    )
    channel_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            JSON().with_variant(JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
    )


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
