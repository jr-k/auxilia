from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.integrations.slack.db_models import SlackToolDiscoveryMode


class AgentSlackBotUpdate(BaseModel):
    enabled: bool = True
    require_mention_in_threads: bool = True
    show_tool_callouts: bool = True
    show_auxilia_link: bool = True
    tool_discovery_mode: SlackToolDiscoveryMode = SlackToolDiscoveryMode.lazy
    bot_token: str | None = Field(default=None, max_length=4096)
    signing_secret: str | None = Field(default=None, max_length=4096)


class AgentSlackBotResponse(BaseModel):
    id: UUID | None = None
    workspace_enabled: bool
    enabled: bool
    require_mention_in_threads: bool
    show_tool_callouts: bool
    show_auxilia_link: bool
    tool_discovery_mode: SlackToolDiscoveryMode
    is_configured: bool
    bot_token_last4: str | None = None
    has_signing_secret: bool = False
    slack_team_id: str | None = None
    slack_team_name: str | None = None
    bot_user_id: str | None = None
    bot_name: str | None = None
    events_url: str
    interactions_url: str
    manifest: dict[str, Any]


class SlackIdentityResponse(BaseModel):
    linked: bool
    workspace_count: int


class SlackLinkCodeResponse(BaseModel):
    code: str
    expires_in: int
