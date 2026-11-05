from __future__ import annotations

import re
from dataclasses import dataclass

import httpx2
from mcp.client.auth.exceptions import OAuthFlowError, OAuthRegistrationError
from pydantic import ValidationError

from app.exceptions import DomainValidationError


@dataclass(frozen=True)
class MCPConnectionFailure:
    code: str
    title: str
    detail: str
    action: str | None = None
    retryable: bool = False


def _exception_tree(exc: BaseException) -> list[BaseException]:
    """Return explicit causes and exception-group leaves without following context."""
    seen: set[int] = set()
    pending = [exc]
    found: list[BaseException] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        found.append(current)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(reversed(current.exceptions))
    return found


def _first(
    errors: list[BaseException], kind: type[BaseException]
) -> BaseException | None:
    return next((error for error in errors if isinstance(error, kind)), None)


def _redirect_uri(message: str) -> str | None:
    match = re.search(r"Redirect URI\s+(https?://\S+)", message, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).rstrip(".,;:)}]\"'")


def _http_status(message: str) -> int | None:
    match = re.search(r"\b([1-5]\d{2})\b", message)
    return int(match.group(1)) if match is not None else None


def classify_mcp_failure(exc: BaseException) -> MCPConnectionFailure:
    """Turn SDK and transport failures into safe, actionable UI copy."""
    errors = _exception_tree(exc)
    messages = [str(error).strip() for error in errors if str(error).strip()]
    message = "\n".join(messages)
    lowered = message.lower()

    registration_error = _first(errors, OAuthRegistrationError)
    if registration_error is not None:
        registration_message = str(registration_error)
        redirect_uri = _redirect_uri(registration_message)
        if "invalid_redirect_uri" in lowered or "redirect uri" in lowered:
            address = f": {redirect_uri}" if redirect_uri is not None else ""
            return MCPConnectionFailure(
                code="oauth_redirect_not_allowed",
                title="OAuth callback address is not allowed",
                detail=(
                    f"The provider rejected Auxilia's OAuth callback address{address}."
                ),
                action=(
                    "Ask the provider to add this exact address to its OAuth "
                    "redirect allowlist, then try again."
                ),
            )
        if _http_status(registration_message) == 403:
            return MCPConnectionFailure(
                code="oauth_registration_denied",
                title="OAuth registration is restricted",
                detail=(
                    "The provider refused to register Auxilia as an OAuth client. "
                    "It may only accept approved MCP clients."
                ),
                action=(
                    "Ask the provider to approve Auxilia or supply OAuth client "
                    "credentials issued for Auxilia."
                ),
            )
        return MCPConnectionFailure(
            code="oauth_registration_failed",
            title="OAuth registration failed",
            detail="The provider could not register Auxilia as an OAuth client.",
            action=(
                "Check the provider's OAuth requirements and configured client "
                "credentials, then try again."
            ),
        )

    if _first(errors, OAuthFlowError) is not None:
        return MCPConnectionFailure(
            code="oauth_setup_failed",
            title="OAuth setup failed",
            detail="The provider could not complete OAuth discovery or setup.",
            action="Check the server URL and OAuth configuration, then try again.",
            retryable=True,
        )

    if _first(errors, ValidationError) is not None:
        return MCPConnectionFailure(
            code="invalid_oauth_configuration",
            title="OAuth configuration is invalid",
            detail=(
                "The saved OAuth configuration is incomplete or no longer "
                "compatible with this server."
            ),
            action="Edit and save the server configuration before trying again.",
        )

    configuration_error = _first(errors, DomainValidationError)
    if configuration_error is not None:
        return MCPConnectionFailure(
            code="invalid_configuration",
            title="Server configuration is incomplete",
            detail=str(configuration_error),
            action="Edit the server configuration, then try again.",
        )

    if (
        _first(errors, httpx2.TimeoutException) is not None
        or _first(errors, TimeoutError) is not None
    ):
        return MCPConnectionFailure(
            code="connection_timeout",
            title="The MCP server took too long to respond",
            detail="Auxilia could not complete the connection within the time limit.",
            action="Check the server status and try again.",
            retryable=True,
        )

    if (
        _first(errors, httpx2.ConnectError) is not None
        or _first(errors, ConnectionError) is not None
    ):
        detail = (
            "Auxilia could not establish a secure connection to the MCP server."
            if any(term in lowered for term in ("ssl", "tls", "certificate"))
            else "Auxilia could not establish a connection to the MCP server."
        )
        return MCPConnectionFailure(
            code="server_unreachable",
            title="The MCP server cannot be reached",
            detail=detail,
            action="Check the server URL, network access, and server status.",
            retryable=True,
        )

    status_error = _first(errors, httpx2.HTTPStatusError)
    status = (
        status_error.response.status_code
        if isinstance(status_error, httpx2.HTTPStatusError)
        else _http_status(message)
    )
    if status in (401, 403):
        return MCPConnectionFailure(
            code="authentication_rejected",
            title="The MCP server rejected the credentials",
            detail="The server returned an authentication or permission error.",
            action="Reconnect your account or verify the configured credentials.",
        )
    if status == 404:
        return MCPConnectionFailure(
            code="endpoint_not_found",
            title="MCP endpoint not found",
            detail="The configured URL does not point to an available MCP endpoint.",
            action="Verify the server URL and its Streamable HTTP path.",
        )
    if status == 429:
        return MCPConnectionFailure(
            code="rate_limited",
            title="The MCP server is rate limiting requests",
            detail="The provider temporarily refused the tools request.",
            action="Wait a moment before trying again.",
            retryable=True,
        )
    if status is not None and status >= 500:
        return MCPConnectionFailure(
            code="server_unavailable",
            title="The MCP server is unavailable",
            detail=f"The provider returned HTTP {status} while loading tools.",
            action="Check the provider's status and try again later.",
            retryable=True,
        )

    if _first(errors, httpx2.RemoteProtocolError) is not None:
        return MCPConnectionFailure(
            code="protocol_error",
            title="The MCP server returned an invalid response",
            detail="The server closed the connection or returned an unsupported response.",
            action="Verify that the URL points to a compatible Streamable HTTP MCP server.",
            retryable=True,
        )

    return MCPConnectionFailure(
        code="tools_unavailable",
        title="Tools could not be loaded",
        detail="The MCP server could not complete the tools request.",
        action="Check the server configuration and status, then try again.",
        retryable=True,
    )
