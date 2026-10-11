from __future__ import annotations

import hashlib
import ipaddress
import secrets
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.settings import auth_settings
from app.exceptions import NotFoundError, PermissionDeniedError
from app.mcp.oauth.models import (
    MCPOAuthAuthorizationRequestDB,
    MCPOAuthClientDB,
    MCPOAuthGrantDB,
)
from app.mcp.oauth.repository import MCPOAuthRepository
from app.mcp.oauth.schemas import (
    MCPOAuthAuthorizationResponse,
    MCPOAuthClientInfo,
    MCPOAuthRedirectResponse,
)
from app.settings import app_settings
from app.users.models import UserDB
from app.utils.encryption import decrypt_value, encrypt_value
from app.workspaces.service import WorkspaceService


SCOPE = "auxilia"
AUTHORIZATION_REQUEST_TTL = timedelta(minutes=10)
AUTHORIZATION_CODE_TTL = timedelta(minutes=5)
ACCESS_TOKEN_TTL = timedelta(hours=1)
REFRESH_TOKEN_TTL = timedelta(days=30)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _opaque_token() -> str:
    return secrets.token_urlsafe(32)


def issuer_url() -> str:
    return app_settings.backend_url.rstrip("/")


def resource_url() -> str:
    return f"{issuer_url()}/mcp"


class AuxiliaAuthorizationCode(AuthorizationCode):
    request_id: UUID
    user_id: UUID
    workspace_id: UUID


class AuxiliaRefreshToken(RefreshToken):
    grant_id: UUID
    user_id: UUID
    workspace_id: UUID


class AuxiliaAccessToken(AccessToken):
    grant_id: UUID
    user_id: UUID
    workspace_id: UUID


class MCPOAuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = MCPOAuthRepository(db)

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = await self.repository.get_client(client_id)
        if row is None:
            return None
        return OAuthClientInformationFull.model_validate(
            {
                **row.metadata_json,
                "client_id": row.client_id,
                "client_secret": (
                    decrypt_value(row.client_secret_encrypted)
                    if row.client_secret_encrypted
                    else None
                ),
            }
        )

    async def register_client(self, client: OAuthClientInformationFull) -> None:
        self._validate_redirect_uris(client)
        metadata = client.model_dump(
            mode="json",
            exclude={"client_id", "client_secret"},
            exclude_none=True,
        )
        try:
            await self.repository.create_client(
                MCPOAuthClientDB(
                    client_id=client.client_id,
                    client_secret_encrypted=(
                        encrypt_value(client.client_secret)
                        if client.client_secret
                        else None
                    ),
                    metadata_json=metadata,
                )
            )
        except IntegrityError as exc:
            raise RegistrationError(
                "invalid_client_metadata", "client_id is already registered"
            ) from exc

    @staticmethod
    def _validate_redirect_uris(client: OAuthClientInformationFull) -> None:
        for value in client.redirect_uris or []:
            parsed = urlparse(str(value))
            if (
                parsed.fragment
                or parsed.username
                or parsed.password
                or not parsed.hostname
            ):
                raise RegistrationError(
                    "invalid_redirect_uri", f"Invalid redirect URI: {value}"
                )
            loopback = parsed.hostname == "localhost"
            with suppress(ValueError):
                loopback = loopback or ipaddress.ip_address(parsed.hostname).is_loopback
            if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
                raise RegistrationError(
                    "invalid_redirect_uri",
                    "Redirect URIs must use HTTPS, except HTTP loopback callbacks",
                )

    async def start_authorization(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        requested_resource = params.resource or resource_url()
        if requested_resource.rstrip("/") != resource_url().rstrip("/"):
            raise AuthorizeError("invalid_target", "Unknown MCP resource")
        scopes = params.scopes or [SCOPE]
        if set(scopes) != {SCOPE}:
            raise AuthorizeError("invalid_scope", "Only the auxilia scope is supported")

        handle = _opaque_token()
        await self.repository.create_authorization_request(
            MCPOAuthAuthorizationRequestDB(
                handle_hash=_digest(handle),
                client_id=client.client_id,
                state=params.state,
                scopes=scopes,
                code_challenge=params.code_challenge,
                redirect_uri=str(params.redirect_uri),
                redirect_uri_provided_explicitly=(
                    params.redirect_uri_provided_explicitly
                ),
                resource=resource_url(),
                expires_at=datetime.now(UTC) + AUTHORIZATION_REQUEST_TTL,
            )
        )
        return (
            f"{auth_settings.FRONTEND_URL.rstrip('/')}/mcp/authorize?request={handle}"
        )

    async def authorization_details(
        self, handle: str, user: UserDB
    ) -> MCPOAuthAuthorizationResponse:
        request = await self._pending_request(handle)
        client = await self.get_client(request.client_id)
        if client is None:
            raise NotFoundError("OAuth client not found")
        workspaces = await WorkspaceService(self.db).list_for_user(user.id)
        return MCPOAuthAuthorizationResponse(
            client=MCPOAuthClientInfo(
                name=client.client_name or "MCP client",
                uri=client.client_uri,
                logo_uri=client.logo_uri,
            ),
            scopes=request.scopes,
            expires_at=request.expires_at,
            workspaces=workspaces,
            active_workspace_id=user.active_workspace_id,
        )

    async def approve(
        self, handle: str, workspace_id: UUID, user: UserDB
    ) -> MCPOAuthRedirectResponse:
        request = await self._pending_request(handle, for_update=True)
        if not await self.repository.has_membership(workspace_id, user.id):
            raise PermissionDeniedError("Workspace access denied")
        code = _opaque_token()
        request.status = "approved"
        request.user_id = user.id
        request.workspace_id = workspace_id
        request.code_hash = _digest(code)
        request.expires_at = datetime.now(UTC) + AUTHORIZATION_CODE_TTL
        self.db.add(request)
        await self.db.flush()
        return MCPOAuthRedirectResponse(
            redirect_url=construct_redirect_uri(
                request.redirect_uri,
                code=code,
                state=request.state,
                iss=issuer_url(),
            )
        )

    async def deny(self, handle: str, user: UserDB) -> MCPOAuthRedirectResponse:
        request = await self._pending_request(handle, for_update=True)
        request.status = "denied"
        request.user_id = user.id
        self.db.add(request)
        await self.db.flush()
        return MCPOAuthRedirectResponse(
            redirect_url=construct_redirect_uri(
                request.redirect_uri,
                error="access_denied",
                error_description="The user denied the request",
                state=request.state,
                iss=issuer_url(),
            )
        )

    async def _pending_request(
        self, handle: str, *, for_update: bool = False
    ) -> MCPOAuthAuthorizationRequestDB:
        row = await self.repository.get_authorization_request(
            _digest(handle), for_update=for_update
        )
        if (
            row is None
            or row.status != "pending"
            or row.expires_at <= datetime.now(UTC)
        ):
            raise NotFoundError("Authorization request not found or expired")
        return row

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, raw_code: str
    ) -> AuxiliaAuthorizationCode | None:
        row = await self.repository.get_authorization_code(_digest(raw_code))
        if (
            row is None
            or row.status != "approved"
            or row.client_id != client.client_id
            or row.user_id is None
            or row.workspace_id is None
        ):
            return None
        return AuxiliaAuthorizationCode(
            code=raw_code,
            scopes=row.scopes,
            expires_at=(row.expires_at.timestamp()),
            client_id=row.client_id,
            code_challenge=row.code_challenge,
            redirect_uri=row.redirect_uri,
            redirect_uri_provided_explicitly=row.redirect_uri_provided_explicitly,
            resource=row.resource,
            subject=str(row.user_id),
            request_id=row.id,
            user_id=row.user_id,
            workspace_id=row.workspace_id,
        )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        code: AuxiliaAuthorizationCode,
    ) -> OAuthToken:
        row = await self.repository.get_authorization_code(
            _digest(code.code), for_update=True
        )
        if (
            row is None
            or row.id != code.request_id
            or row.status != "approved"
            or row.client_id != client.client_id
            or row.user_id is None
            or row.workspace_id is None
            or row.expires_at <= datetime.now(UTC)
        ):
            raise TokenError("invalid_grant", "Authorization code is no longer valid")
        if not await self.repository.has_membership(row.workspace_id, row.user_id):
            raise TokenError("invalid_grant", "Workspace access was revoked")

        access, refresh = _opaque_token(), _opaque_token()
        now = datetime.now(UTC)
        grant = MCPOAuthGrantDB(
            client_id=row.client_id,
            user_id=row.user_id,
            workspace_id=row.workspace_id,
            scopes=row.scopes,
            resource=row.resource,
            access_token_hash=_digest(access),
            access_expires_at=now + ACCESS_TOKEN_TTL,
            refresh_token_hash=_digest(refresh),
            refresh_expires_at=now + REFRESH_TOKEN_TTL,
        )
        await self.repository.create_grant(grant)
        row.status = "consumed"
        self.db.add(row)
        await self.db.flush()
        return self._token_response(access, refresh, grant.scopes)

    async def load_access_token(self, raw_token: str) -> AuxiliaAccessToken | None:
        grant = await self.repository.get_access_grant(_digest(raw_token))
        if not await self._grant_is_valid(grant, access=True):
            return None
        assert grant is not None
        return AuxiliaAccessToken(
            token=raw_token,
            client_id=grant.client_id,
            scopes=grant.scopes,
            expires_at=int(grant.access_expires_at.timestamp()),
            resource=grant.resource,
            subject=str(grant.user_id),
            claims={
                "iss": issuer_url(),
                "workspace_id": str(grant.workspace_id),
            },
            grant_id=grant.id,
            user_id=grant.user_id,
            workspace_id=grant.workspace_id,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, raw_token: str
    ) -> AuxiliaRefreshToken | None:
        grant = await self.repository.get_refresh_grant(_digest(raw_token))
        if (
            not await self._grant_is_valid(grant, access=False)
            or grant is None
            or grant.client_id != client.client_id
        ):
            return None
        return AuxiliaRefreshToken(
            token=raw_token,
            client_id=grant.client_id,
            scopes=grant.scopes,
            expires_at=int(grant.refresh_expires_at.timestamp()),
            resource=grant.resource,
            subject=str(grant.user_id),
            grant_id=grant.id,
            user_id=grant.user_id,
            workspace_id=grant.workspace_id,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        token: AuxiliaRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        grant = await self.repository.get_grant_for_update(token.grant_id)
        if (
            grant is None
            or grant.client_id != client.client_id
            or grant.refresh_token_hash != _digest(token.token)
            or not await self._grant_is_valid(grant, access=False)
        ):
            raise TokenError("invalid_grant", "Refresh token is no longer valid")
        if not set(scopes).issubset(grant.scopes):
            raise TokenError("invalid_scope", "Requested scope was not granted")
        access, refresh = _opaque_token(), _opaque_token()
        now = datetime.now(UTC)
        grant.scopes = scopes
        grant.access_token_hash = _digest(access)
        grant.access_expires_at = now + ACCESS_TOKEN_TTL
        grant.refresh_token_hash = _digest(refresh)
        grant.refresh_expires_at = now + REFRESH_TOKEN_TTL
        self.db.add(grant)
        await self.db.flush()
        return self._token_response(access, refresh, scopes)

    async def revoke_token(self, raw_token: str) -> None:
        token_hash = _digest(raw_token)
        grant = await self.repository.get_access_grant(token_hash, for_update=True)
        if grant is None:
            grant = await self.repository.get_refresh_grant(token_hash, for_update=True)
        if grant is not None and grant.revoked_at is None:
            grant.revoked_at = datetime.now(UTC)
            self.db.add(grant)
            await self.db.flush()

    async def _grant_is_valid(
        self, grant: MCPOAuthGrantDB | None, *, access: bool
    ) -> bool:
        if grant is None or grant.revoked_at is not None:
            return False
        expiry = grant.access_expires_at if access else grant.refresh_expires_at
        return expiry > datetime.now(UTC) and await self.repository.has_membership(
            grant.workspace_id, grant.user_id
        )

    @staticmethod
    def _token_response(
        access_token: str, refresh_token: str, scopes: list[str]
    ) -> OAuthToken:
        return OAuthToken(
            access_token=access_token,
            expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
            refresh_token=refresh_token,
            scope=" ".join(scopes),
        )
