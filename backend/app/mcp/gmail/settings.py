"""Shared configuration for Auxilia's Gmail MCP endpoint."""

from app.settings import app_settings


GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]


def gmail_mcp_base_url() -> str:
    return f"{app_settings.backend_url.rstrip('/')}/gmail"


def gmail_mcp_url() -> str:
    return f"{gmail_mcp_base_url()}/mcp"
