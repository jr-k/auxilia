from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.notifications.models import NotificationChannelType


class NotificationChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    channel_type: NotificationChannelType
    enabled: bool = True
    is_default: bool = False
    config: dict = Field(default_factory=dict)


class NotificationChannelPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    is_default: bool | None = None
    config: dict | None = None


class NotificationChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    channel_type: NotificationChannelType
    enabled: bool
    is_default: bool
    config: dict
    created_at: datetime
    updated_at: datetime


class NotificationChannelTestResponse(BaseModel):
    delivered: list[str] = Field(default_factory=list)
    failed: dict[str, str] = Field(default_factory=dict)


class SlackNotificationSettingsResponse(BaseModel):
    enabled: bool
    is_configured: bool
    bot_token_last4: str | None = None
    bot_token_length: int | None = None
    has_signing_secret: bool = False
    slack_team_id: str | None = None
    events_url: str
    interactions_url: str


class SlackNotificationSettingsUpdate(BaseModel):
    enabled: bool = True
    bot_token: str | None = Field(default=None, max_length=4096)
    signing_secret: str | None = Field(default=None, max_length=4096)
    slack_team_id: str | None = Field(default=None, max_length=64)
