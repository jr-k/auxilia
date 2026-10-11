from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationParams,
    IdentityAssertionParams,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from app.database import AsyncSessionLocal
from app.mcp.oauth.service import (
    AuxiliaAccessToken,
    AuxiliaAuthorizationCode,
    AuxiliaRefreshToken,
    MCPOAuthService,
)


@asynccontextmanager
async def _service():
    async with AsyncSessionLocal() as db:
        try:
            yield MCPOAuthService(db)
        except Exception:
            await db.rollback()
            raise
        else:
            await db.commit()


class AuxiliaOAuthProvider:
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        async with _service() as service:
            return await service.get_client(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        async with _service() as service:
            await service.register_client(client_info)

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        async with _service() as service:
            return await service.start_authorization(client, params)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuxiliaAuthorizationCode | None:
        async with _service() as service:
            return await service.load_authorization_code(client, authorization_code)

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuxiliaAuthorizationCode,
    ) -> OAuthToken:
        async with _service() as service:
            return await service.exchange_authorization_code(client, authorization_code)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> AuxiliaRefreshToken | None:
        async with _service() as service:
            return await service.load_refresh_token(client, refresh_token)

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: AuxiliaRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        async with _service() as service:
            return await service.exchange_refresh_token(client, refresh_token, scopes)

    async def load_access_token(self, token: str) -> AuxiliaAccessToken | None:
        async with _service() as service:
            return await service.load_access_token(token)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        async with _service() as service:
            await service.revoke_token(token.token)

    async def exchange_identity_assertion(
        self,
        client: OAuthClientInformationFull,
        params: IdentityAssertionParams,
    ) -> OAuthToken:
        del client, params
        raise TokenError(
            "unsupported_grant_type",
            "Identity assertion grants are not supported",
        )


auxilia_oauth_provider = AuxiliaOAuthProvider()
