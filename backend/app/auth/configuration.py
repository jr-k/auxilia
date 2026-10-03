from dataclasses import dataclass

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import WorkspaceAuthenticationRepository
from app.auth.schemas import (
    WorkspaceAuthenticationResponse,
    WorkspaceAuthenticationUpdate,
)
from app.auth.settings import auth_settings
from app.database import get_db
from app.exceptions import DomainValidationError


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    google_exclusive: bool


class WorkspaceAuthenticationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = WorkspaceAuthenticationRepository(db)

    @property
    def callback_url(self) -> str:
        return f"{auth_settings.FRONTEND_URL}/api/backend/auth/google/callback"

    async def get_runtime_config(self) -> GoogleOAuthConfig | None:
        credentials = await self.repository.get_credentials()
        if credentials is None:
            return None
        row = await self.repository.get_settings()
        return GoogleOAuthConfig(
            client_id=credentials[0],
            client_secret=credentials[1],
            google_exclusive=bool(row and row.google_exclusive),
        )

    async def password_enabled(self) -> bool:
        config = await self.get_runtime_config()
        return config is None or not config.google_exclusive

    async def get_response(self) -> WorkspaceAuthenticationResponse:
        row = await self.repository.get_settings()
        credentials = await self.repository.get_credentials()
        client_id = credentials[0] if credentials else None
        return WorkspaceAuthenticationResponse(
            enabled=bool(row and row.enabled),
            is_configured=credentials is not None,
            google_exclusive=bool(row and row.google_exclusive),
            client_id_last4=client_id[-4:] if client_id else None,
            client_id_length=len(client_id) if client_id else None,
            callback_url=self.callback_url,
        )

    async def update(
        self, data: WorkspaceAuthenticationUpdate
    ) -> WorkspaceAuthenticationResponse:
        existing = await self.repository.get_settings()
        has_existing_pair = bool(
            existing
            and existing.google_client_id_encrypted
            and existing.google_client_secret_encrypted
        )
        client_id = data.client_id.strip() if data.client_id is not None else None
        client_secret = (
            data.client_secret.strip() if data.client_secret is not None else None
        )
        if (client_id is None) != (client_secret is None):
            raise DomainValidationError(
                "Google client ID and client secret must be updated together"
            )
        if client_id == "" or client_secret == "":
            raise DomainValidationError("Google credentials cannot be empty")
        if data.enabled and not has_existing_pair and client_id is None:
            raise DomainValidationError(
                "Google client ID and client secret are required"
            )
        await self.repository.save(
            enabled=data.enabled,
            google_exclusive=data.google_exclusive if data.enabled else False,
            client_id=client_id,
            client_secret=client_secret,
        )
        return await self.get_response()

    async def clear(self) -> WorkspaceAuthenticationResponse:
        await self.repository.clear()
        return await self.get_response()

    async def build_oauth(self) -> OAuth | None:
        config = await self.get_runtime_config()
        if config is None:
            return None
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=config.client_id,
            client_secret=config.client_secret,
            server_metadata_url=(
                "https://accounts.google.com/.well-known/openid-configuration"
            ),
            client_kwargs={"scope": "openid email profile"},
        )
        return oauth


def get_workspace_authentication_service(
    db: AsyncSession = Depends(get_db),
) -> WorkspaceAuthenticationService:
    return WorkspaceAuthenticationService(db)
