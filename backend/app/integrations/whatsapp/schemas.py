from uuid import UUID

from pydantic import BaseModel, Field

from app.integrations.whatsapp.db_models import WhatsAppToolDiscoveryMode


class WhatsAppWorkspaceSettingsResponse(BaseModel):
    enabled: bool


class WhatsAppWorkspaceSettingsUpdate(BaseModel):
    enabled: bool


class WhatsAppConnectionUpdate(BaseModel):
    enabled: bool = True
    show_typing_indicator: bool = True
    show_tool_callouts: bool = True
    show_auxilia_link: bool = True
    tool_discovery_mode: WhatsAppToolDiscoveryMode = WhatsAppToolDiscoveryMode.lazy
    business_account_id: str | None = Field(default=None, max_length=64)
    phone_number_id: str | None = Field(default=None, max_length=64)
    access_token: str | None = Field(default=None, max_length=8192)
    app_secret: str | None = Field(default=None, max_length=4096)


class WhatsAppConnectionResponse(BaseModel):
    id: UUID | None = None
    agent_id: UUID
    workspace_enabled: bool
    enabled: bool
    show_typing_indicator: bool
    show_tool_callouts: bool
    show_auxilia_link: bool
    tool_discovery_mode: WhatsAppToolDiscoveryMode
    is_configured: bool
    access_token_last4: str | None = None
    has_app_secret: bool
    business_account_id: str | None = None
    phone_number_id: str | None = None
    display_phone_number: str | None = None
    verified_name: str | None = None
    webhook_url: str
    verify_token: str | None = None
    deep_link_url: str | None = None


class WhatsAppIdentityResponse(BaseModel):
    linked: bool
    phone_number: str | None = None
    display_name: str | None = None


class WhatsAppLinkCodeResponse(BaseModel):
    code: str
    expires_in: int
    deep_link_url: str | None = None
