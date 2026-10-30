from uuid import UUID

from pydantic import BaseModel, Field

from app.integrations.telegram.db_models import TelegramToolDiscoveryMode


class TelegramWorkspaceSettingsResponse(BaseModel):
    enabled: bool


class TelegramWorkspaceSettingsUpdate(BaseModel):
    enabled: bool


class TelegramBotUpdate(BaseModel):
    enabled: bool = True
    require_mention_in_groups: bool = True
    show_tool_callouts: bool = True
    tool_discovery_mode: TelegramToolDiscoveryMode = (
        TelegramToolDiscoveryMode.all_capabilities
    )
    bot_token: str | None = Field(default=None, max_length=4096)


class TelegramBotResponse(BaseModel):
    id: UUID | None = None
    agent_id: UUID
    workspace_enabled: bool
    enabled: bool
    require_mention_in_groups: bool
    show_tool_callouts: bool
    tool_discovery_mode: TelegramToolDiscoveryMode
    is_configured: bool
    bot_token_last4: str | None = None
    bot_id: str | None = None
    bot_username: str | None = None
    bot_name: str | None = None
    webhook_url: str
    deep_link_url: str | None = None


class TelegramIdentityResponse(BaseModel):
    linked: bool
    username: str | None = None
    display_name: str | None = None


class TelegramLinkCodeResponse(BaseModel):
    code: str
    expires_in: int
    deep_link_url: str | None = None
