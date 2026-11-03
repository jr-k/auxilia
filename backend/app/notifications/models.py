from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum as SAEnum,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models import BaseDBModel


class SlackNotificationSettingsDB(BaseDBModel, table=True):
    __tablename__ = "slack_notification_settings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "key", name="uq_slack_notifications_workspace_key"
        ),
    )

    workspace_id: UUID = Field(foreign_key="workspaces.id", index=True)
    key: str = Field(default="default", nullable=False)
    enabled: bool = Field(default=False, nullable=False)


class WebPushSubscriptionDB(BaseDBModel, table=True):
    __tablename__ = "web_push_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "endpoint_hash",
            name="uq_web_push_subscriptions_endpoint_hash",
        ),
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    endpoint_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    endpoint_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    p256dh_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    auth_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    user_agent: str | None = Field(
        default=None,
        sa_column=Column(String(512), nullable=True),
    )


class WebPushDeliveryStatus(str, Enum):
    pending = "pending"
    processing = "processing"


def _payload_column() -> Column:
    return Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )


class WebPushDeliveryDB(BaseDBModel, table=True):
    __tablename__ = "web_push_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "run_id",
            name="uq_web_push_deliveries_subscription_run",
        ),
        Index(
            "ix_web_push_deliveries_pending",
            "status",
            "next_attempt_at",
        ),
    )

    subscription_id: UUID = Field(
        foreign_key="web_push_subscriptions.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    run_id: str = Field(sa_column=Column(String, nullable=False, index=True))
    status: WebPushDeliveryStatus = Field(
        default=WebPushDeliveryStatus.pending,
        sa_column=Column(
            SAEnum(
                WebPushDeliveryStatus,
                native_enum=False,
                create_constraint=False,
                length=20,
            ),
            nullable=False,
            server_default=WebPushDeliveryStatus.pending.value,
        ),
    )
    attempts: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    next_attempt_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    claimed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    payload: dict = Field(sa_column=_payload_column())
    last_error: str | None = Field(
        default=None,
        sa_column=Column(String(128), nullable=True),
    )
