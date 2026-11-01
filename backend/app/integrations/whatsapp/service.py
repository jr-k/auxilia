import json
import secrets
import string
from dataclasses import dataclass
from urllib.parse import quote
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.repository import AgentRepository
from app.auth.settings import auth_settings
from app.database import get_db
from app.exceptions import (
    AlreadyExistsError,
    DomainValidationError,
    NotFoundError,
)
from app.integrations.whatsapp.client import WhatsAppAPIError, WhatsAppClient
from app.integrations.whatsapp.db_models import (
    AgentWhatsAppConnectionDB,
    WhatsAppIdentityDB,
    WhatsAppToolDiscoveryMode,
    WhatsAppWorkspaceSettingsDB,
)
from app.integrations.whatsapp.repository import (
    AgentWhatsAppConnectionRepository,
    WhatsAppIdentityRepository,
    WhatsAppThreadBindingRepository,
    WhatsAppWorkspaceSettingsRepository,
)
from app.integrations.whatsapp.schemas import (
    WhatsAppConnectionResponse,
    WhatsAppConnectionUpdate,
    WhatsAppIdentityResponse,
    WhatsAppLinkCodeResponse,
    WhatsAppWorkspaceSettingsResponse,
)
from app.redis_client import get_redis
from app.utils.encryption import decrypt_value, encrypt_value
from app.workspaces.dependencies import get_active_workspace_id
from app.workspaces.repository import WorkspaceRepository


LINK_TTL_SECONDS = 600
LINK_PREFIX = "whatsapp:link:"


@dataclass(frozen=True)
class WhatsAppRuntimeConfig:
    id: UUID
    workspace_id: UUID
    agent_id: UUID
    workspace_enabled: bool
    enabled: bool
    show_typing_indicator: bool
    show_tool_callouts: bool
    show_auxilia_link: bool
    tool_discovery_mode: WhatsAppToolDiscoveryMode
    business_account_id: str
    phone_number_id: str
    display_phone_number: str | None
    verified_name: str | None
    access_token: str
    app_secret: str
    verify_token: str


class WhatsAppWorkspaceSettingsService:
    def __init__(self, db: AsyncSession, workspace_id: UUID):
        self.db = db
        self.workspace_id = workspace_id
        self.repository = WhatsAppWorkspaceSettingsRepository(db)

    async def get_response(self) -> WhatsAppWorkspaceSettingsResponse:
        row = await self.repository.get_for_workspace(self.workspace_id)
        return WhatsAppWorkspaceSettingsResponse(enabled=bool(row and row.enabled))

    async def update(self, enabled: bool) -> WhatsAppWorkspaceSettingsResponse:
        row = await self.repository.get_for_workspace(self.workspace_id)
        if row is None:
            row = WhatsAppWorkspaceSettingsDB(
                workspace_id=self.workspace_id, enabled=enabled
            )
        else:
            row.enabled = enabled
        self.db.add(row)
        await self.db.flush()
        return await self.get_response()


class WhatsAppConnectionService:
    def __init__(self, db: AsyncSession, workspace_id: UUID | None = None):
        self.db = db
        self.workspace_id = workspace_id
        self.repository = AgentWhatsAppConnectionRepository(db)
        self.workspace_settings = WhatsAppWorkspaceSettingsRepository(db)

    @staticmethod
    def _webhook_url(connection_id: UUID | None) -> str:
        suffix = str(connection_id) if connection_id else "CONNECTION_ID"
        return (
            f"{auth_settings.FRONTEND_URL}/api/backend/integrations/whatsapp/"
            f"{suffix}/webhook"
        )

    async def _workspace_enabled(self, workspace_id: UUID) -> bool:
        row = await self.workspace_settings.get_for_workspace(workspace_id)
        return bool(row and row.enabled)

    async def _ensure_agent(self, workspace_id: UUID, agent_id: UUID) -> None:
        if await AgentRepository(self.db, workspace_id).get_scoped(agent_id) is None:
            raise NotFoundError("Agent not found")

    def _response(
        self,
        workspace_enabled: bool,
        row: AgentWhatsAppConnectionDB | None,
        *,
        agent_id: UUID,
    ) -> WhatsAppConnectionResponse:
        display_digits = (
            "".join(
                character
                for character in row.display_phone_number
                if character.isdigit()
            )
            if row and row.display_phone_number
            else ""
        )
        return WhatsAppConnectionResponse(
            id=row.id if row else None,
            agent_id=agent_id,
            workspace_enabled=workspace_enabled,
            enabled=row.enabled if row else True,
            show_typing_indicator=row.show_typing_indicator if row else True,
            show_tool_callouts=row.show_tool_callouts if row else True,
            show_auxilia_link=row.show_auxilia_link if row else True,
            tool_discovery_mode=(
                row.tool_discovery_mode if row else WhatsAppToolDiscoveryMode.lazy
            ),
            is_configured=row is not None,
            access_token_last4=(
                decrypt_value(row.access_token_encrypted)[-4:] if row else None
            ),
            has_app_secret=row is not None,
            business_account_id=row.business_account_id if row else None,
            phone_number_id=row.phone_number_id if row else None,
            display_phone_number=row.display_phone_number if row else None,
            verified_name=row.verified_name if row else None,
            webhook_url=self._webhook_url(row.id if row else None),
            verify_token=(decrypt_value(row.verify_token_encrypted) if row else None),
            deep_link_url=(
                f"https://wa.me/{display_digits}" if display_digits else None
            ),
        )

    async def get_setup(self, agent_id: UUID) -> WhatsAppConnectionResponse:
        workspace_id = self._require_workspace()
        await self._ensure_agent(workspace_id, agent_id)
        return self._response(
            await self._workspace_enabled(workspace_id), None, agent_id=agent_id
        )

    async def list_connections(
        self, agent_id: UUID
    ) -> list[WhatsAppConnectionResponse]:
        workspace_id = self._require_workspace()
        await self._ensure_agent(workspace_id, agent_id)
        rows = await self.repository.list_for_agent(workspace_id, agent_id)
        enabled = await self._workspace_enabled(workspace_id)
        return [self._response(enabled, row, agent_id=agent_id) for row in rows]

    async def get_runtime(self, connection_id: UUID) -> WhatsAppRuntimeConfig | None:
        row = await self.repository.get(connection_id)
        if row is None:
            return None
        return WhatsAppRuntimeConfig(
            id=row.id,
            workspace_id=row.workspace_id,
            agent_id=row.agent_id,
            workspace_enabled=await self._workspace_enabled(row.workspace_id),
            enabled=row.enabled,
            show_typing_indicator=row.show_typing_indicator,
            show_tool_callouts=row.show_tool_callouts,
            show_auxilia_link=row.show_auxilia_link,
            tool_discovery_mode=row.tool_discovery_mode,
            business_account_id=row.business_account_id,
            phone_number_id=row.phone_number_id,
            display_phone_number=row.display_phone_number,
            verified_name=row.verified_name,
            access_token=decrypt_value(row.access_token_encrypted),
            app_secret=decrypt_value(row.app_secret_encrypted),
            verify_token=decrypt_value(row.verify_token_encrypted),
        )

    async def create(
        self, agent_id: UUID, data: WhatsAppConnectionUpdate
    ) -> WhatsAppConnectionResponse:
        workspace_id = self._require_workspace()
        await self._ensure_agent(workspace_id, agent_id)
        business_account_id = (data.business_account_id or "").strip()
        phone_number_id = (data.phone_number_id or "").strip()
        access_token = (data.access_token or "").strip()
        app_secret = (data.app_secret or "").strip()
        if not all((business_account_id, phone_number_id, access_token, app_secret)):
            raise DomainValidationError(
                "Business account ID, phone number ID, access token and app secret "
                "are required"
            )
        if await self.repository.get_by_phone_number_id(phone_number_id):
            raise AlreadyExistsError("This WhatsApp phone number is already connected")
        phone = await self._validate_credentials(
            access_token, business_account_id, phone_number_id
        )
        row = AgentWhatsAppConnectionDB(
            workspace_id=workspace_id,
            agent_id=agent_id,
            enabled=data.enabled,
            show_typing_indicator=data.show_typing_indicator,
            show_tool_callouts=data.show_tool_callouts,
            show_auxilia_link=data.show_auxilia_link,
            tool_discovery_mode=data.tool_discovery_mode,
            business_account_id=business_account_id,
            phone_number_id=phone_number_id,
            display_phone_number=str(phone.get("display_phone_number") or "") or None,
            verified_name=str(phone.get("verified_name") or "") or None,
            access_token_encrypted=encrypt_value(access_token),
            app_secret_encrypted=encrypt_value(app_secret),
            verify_token_encrypted=encrypt_value(secrets.token_urlsafe(32)),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return self._response(
            await self._workspace_enabled(workspace_id), row, agent_id=agent_id
        )

    async def update(
        self,
        agent_id: UUID,
        connection_id: UUID,
        data: WhatsAppConnectionUpdate,
    ) -> WhatsAppConnectionResponse:
        workspace_id = self._require_workspace()
        row = await self.repository.get_for_scope(workspace_id, agent_id, connection_id)
        if row is None:
            raise NotFoundError("WhatsApp connection not found")
        business_account_id = (
            data.business_account_id.strip()
            if data.business_account_id is not None
            else row.business_account_id
        )
        phone_number_id = (
            data.phone_number_id.strip()
            if data.phone_number_id is not None
            else row.phone_number_id
        )
        access_token = (
            data.access_token.strip()
            if data.access_token is not None
            else decrypt_value(row.access_token_encrypted)
        )
        app_secret = (
            data.app_secret.strip()
            if data.app_secret is not None
            else decrypt_value(row.app_secret_encrypted)
        )
        if not all((business_account_id, phone_number_id, access_token, app_secret)):
            raise DomainValidationError("WhatsApp credentials cannot be empty")
        existing = await self.repository.get_by_phone_number_id(phone_number_id)
        if existing is not None and existing.id != row.id:
            raise AlreadyExistsError("This WhatsApp phone number is already connected")
        phone = await self._validate_credentials(
            access_token, business_account_id, phone_number_id
        )
        row.enabled = data.enabled
        row.show_typing_indicator = data.show_typing_indicator
        row.show_tool_callouts = data.show_tool_callouts
        row.show_auxilia_link = data.show_auxilia_link
        row.tool_discovery_mode = data.tool_discovery_mode
        row.business_account_id = business_account_id
        row.phone_number_id = phone_number_id
        row.display_phone_number = str(phone.get("display_phone_number") or "") or None
        row.verified_name = str(phone.get("verified_name") or "") or None
        row.access_token_encrypted = encrypt_value(access_token)
        row.app_secret_encrypted = encrypt_value(app_secret)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return self._response(
            await self._workspace_enabled(workspace_id), row, agent_id=agent_id
        )

    async def delete(self, agent_id: UUID, connection_id: UUID) -> None:
        workspace_id = self._require_workspace()
        row = await self.repository.get_for_scope(workspace_id, agent_id, connection_id)
        if row is None:
            raise NotFoundError("WhatsApp connection not found")
        await self.db.delete(row)
        await self.db.flush()

    async def _validate_credentials(
        self, token: str, business_account_id: str, phone_number_id: str
    ) -> dict:
        client = WhatsAppClient(token, phone_number_id)
        try:
            phone = await client.get_phone_number()
            numbers = await client.list_business_phone_numbers(business_account_id)
        except WhatsAppAPIError as exc:
            raise DomainValidationError(
                "Could not validate the WhatsApp Cloud API credentials"
            ) from exc
        if str(phone.get("id") or "") != phone_number_id or not any(
            str(candidate.get("id") or "") == phone_number_id for candidate in numbers
        ):
            raise DomainValidationError(
                "The phone number ID does not belong to this WhatsApp Business Account"
            )
        return phone

    def _require_workspace(self) -> UUID:
        if self.workspace_id is None:
            raise RuntimeError("A workspace is required for WhatsApp settings")
        return self.workspace_id


class WhatsAppIdentityService:
    def __init__(self, db: AsyncSession, workspace_id: UUID):
        self.db = db
        self.workspace_id = workspace_id
        self.repository = WhatsAppIdentityRepository(db)
        self.bindings = WhatsAppThreadBindingRepository(db)

    async def get_response(self, user_id: UUID) -> WhatsAppIdentityResponse:
        row = await self.repository.get_for_user(self.workspace_id, user_id)
        return WhatsAppIdentityResponse(
            linked=row is not None,
            phone_number=row.phone_number if row else None,
            display_name=row.display_name if row else None,
        )

    async def create_link_code(self, user_id: UUID) -> WhatsAppLinkCodeResponse:
        alphabet = string.ascii_uppercase + string.digits
        payload = json.dumps(
            {"workspace_id": str(self.workspace_id), "user_id": str(user_id)}
        )
        redis = get_redis()
        code = ""
        for _ in range(8):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            if await redis.set(
                f"{LINK_PREFIX}{code}", payload, ex=LINK_TTL_SECONDS, nx=True
            ):
                break
        else:
            raise RuntimeError("Could not allocate a WhatsApp link code")
        connections = await AgentWhatsAppConnectionRepository(
            self.db
        ).list_for_workspace(self.workspace_id)
        display = next(
            (
                row.display_phone_number
                for row in connections
                if row.enabled and row.display_phone_number
            ),
            None,
        )
        digits = (
            "".join(character for character in display if character.isdigit())
            if display
            else ""
        )
        message = quote(f"/link {code}")
        return WhatsAppLinkCodeResponse(
            code=code,
            expires_in=LINK_TTL_SECONDS,
            deep_link_url=(
                f"https://wa.me/{digits}?text={message}" if digits else None
            ),
        )

    async def consume_link_code(
        self,
        *,
        whatsapp_user_id: str,
        phone_number: str | None,
        display_name: str | None,
        code: str,
    ) -> WhatsAppIdentityDB:
        key = f"{LINK_PREFIX}{code.strip().upper()}"
        redis = get_redis()
        raw = await redis.get(key)
        if not raw:
            raise DomainValidationError("This link code is invalid or expired")
        payload = json.loads(raw)
        if payload.get("workspace_id") != str(self.workspace_id):
            raise DomainValidationError("This link code belongs to another workspace")
        if await redis.getdel(key) is None:
            raise DomainValidationError("This link code was already used")
        user_id = UUID(payload["user_id"])
        if (
            await WorkspaceRepository(self.db).get_membership(
                self.workspace_id, user_id
            )
            is None
        ):
            raise NotFoundError("Workspace membership not found")
        external = await self.repository.get_external(
            self.workspace_id, whatsapp_user_id
        )
        if external is not None and external.user_id != user_id:
            raise AlreadyExistsError("This WhatsApp account is already linked")
        previous = await self.repository.get_for_user(self.workspace_id, user_id)
        if previous is not None and previous.whatsapp_user_id != whatsapp_user_id:
            connections = await AgentWhatsAppConnectionRepository(
                self.db
            ).list_for_workspace(self.workspace_id)
            await self.bindings.delete_for_identity(
                [row.id for row in connections], previous.whatsapp_user_id
            )
            await self.repository.unlink(self.workspace_id, user_id)
        row = external or WhatsAppIdentityDB(
            workspace_id=self.workspace_id,
            whatsapp_user_id=whatsapp_user_id,
            user_id=user_id,
        )
        row.phone_number = phone_number
        row.display_name = display_name
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def unlink(self, user_id: UUID) -> None:
        identity = await self.repository.get_for_user(self.workspace_id, user_id)
        if identity is None:
            return
        connections = await AgentWhatsAppConnectionRepository(
            self.db
        ).list_for_workspace(self.workspace_id)
        await self.bindings.delete_for_identity(
            [row.id for row in connections], identity.whatsapp_user_id
        )
        await self.repository.unlink(self.workspace_id, user_id)


def get_whatsapp_connection_service(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_active_workspace_id),
) -> WhatsAppConnectionService:
    return WhatsAppConnectionService(db, workspace_id)


def get_whatsapp_workspace_service(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_active_workspace_id),
) -> WhatsAppWorkspaceSettingsService:
    return WhatsAppWorkspaceSettingsService(db, workspace_id)
