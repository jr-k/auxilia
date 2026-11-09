"""Best-effort RFC 7009 revocation for personal outbound MCP OAuth tokens."""

from __future__ import annotations

import logging
from typing import Literal

import httpx2
from mcp.shared.auth import OAuthClientInformationFull, OAuthMetadata, OAuthToken


logger = logging.getLogger(__name__)

ProviderRevocationStatus = Literal["succeeded", "unsupported", "failed"]
_REVOCATION_TIMEOUT_SECONDS = 5.0
_AUTH_NONE = "none"
_AUTH_POST = "client_secret_post"
_AUTH_BASIC = "client_secret_basic"


async def revoke_oauth_tokens(
    *,
    server_id: str,
    tokens: OAuthToken,
    metadata: OAuthMetadata | None,
    client_info: OAuthClientInformationFull | None,
) -> ProviderRevocationStatus:
    """Revoke the stored token pair when the provider advertises RFC 7009.

    Failure is deliberately a return value. The caller must always complete
    local deletion even when the provider is unavailable or rejects revocation.
    """
    if metadata is None or metadata.revocation_endpoint is None:
        return "unsupported"
    if client_info is None:
        return "unsupported"

    method = client_info.token_endpoint_auth_method or _AUTH_NONE
    advertised = metadata.revocation_endpoint_auth_methods_supported
    if advertised is not None and method not in advertised:
        return "unsupported"
    if method not in {_AUTH_NONE, _AUTH_POST, _AUTH_BASIC}:
        return "unsupported"
    if method in {_AUTH_POST, _AUTH_BASIC} and not client_info.client_secret:
        return "unsupported"

    token_values: list[tuple[str, str]] = []
    if tokens.refresh_token:
        token_values.append((tokens.refresh_token, "refresh_token"))
    token_values.append((tokens.access_token, "access_token"))

    try:
        async with httpx2.AsyncClient(
            follow_redirects=False,
            timeout=_REVOCATION_TIMEOUT_SECONDS,
            headers={"User-Agent": "auxilia"},
        ) as client:
            for token, hint in token_values:
                data = {"token": token, "token_type_hint": hint}
                auth: httpx2.Auth | None = None
                if method == _AUTH_NONE:
                    data["client_id"] = client_info.client_id
                elif method == _AUTH_POST:
                    data["client_id"] = client_info.client_id
                    data["client_secret"] = client_info.client_secret or ""
                else:
                    auth = httpx2.BasicAuth(
                        client_info.client_id, client_info.client_secret or ""
                    )
                if auth is None:
                    response = await client.post(
                        str(metadata.revocation_endpoint), data=data
                    )
                else:
                    response = await client.post(
                        str(metadata.revocation_endpoint),
                        data=data,
                        auth=auth,
                    )
                response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - remote failure must not block local deletion
        logger.warning(
            "OAuth provider revocation failed for MCP server %s (%s)",
            server_id,
            type(exc).__name__,
        )
        return "failed"

    return "succeeded"
