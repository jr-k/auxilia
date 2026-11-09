from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.shared.auth import OAuthClientInformationFull, OAuthMetadata, OAuthToken

from app.mcp.client import revocation as revocation_module
from app.mcp.client.revocation import revoke_oauth_tokens


def _metadata(*, with_endpoint: bool = True) -> OAuthMetadata:
    return OAuthMetadata(
        issuer="https://provider.example.com",
        authorization_endpoint="https://provider.example.com/authorize",
        token_endpoint="https://provider.example.com/token",
        revocation_endpoint=(
            "https://provider.example.com/revoke" if with_endpoint else None
        ),
        revocation_endpoint_auth_methods_supported=["client_secret_post"],
    )


def _client_info() -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id="client-id",
        client_secret="client-secret",
        token_endpoint_auth_method="client_secret_post",
    )


@pytest.mark.asyncio
async def test_revocation_is_unsupported_without_advertised_endpoint():
    status = await revoke_oauth_tokens(
        server_id="server-id",
        tokens=OAuthToken(access_token="access", refresh_token="refresh"),
        metadata=_metadata(with_endpoint=False),
        client_info=_client_info(),
    )

    assert status == "unsupported"


@pytest.mark.asyncio
async def test_revocation_attempts_refresh_and_access_tokens(monkeypatch):
    response = MagicMock()
    response.raise_for_status.return_value = None
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(
        revocation_module.httpx2, "AsyncClient", MagicMock(return_value=client)
    )

    status = await revoke_oauth_tokens(
        server_id="server-id",
        tokens=OAuthToken(access_token="access", refresh_token="refresh"),
        metadata=_metadata(),
        client_info=_client_info(),
    )

    assert status == "succeeded"
    assert client.post.await_count == 2
    first_data = client.post.await_args_list[0].kwargs["data"]
    second_data = client.post.await_args_list[1].kwargs["data"]
    assert first_data["token_type_hint"] == "refresh_token"
    assert second_data["token_type_hint"] == "access_token"


@pytest.mark.asyncio
async def test_provider_failure_is_returned_without_raising(monkeypatch):
    client = MagicMock()
    client.post = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(
        revocation_module.httpx2, "AsyncClient", MagicMock(return_value=client)
    )

    status = await revoke_oauth_tokens(
        server_id="server-id",
        tokens=OAuthToken(access_token="access"),
        metadata=_metadata(),
        client_info=_client_info(),
    )

    assert status == "failed"
