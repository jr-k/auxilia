import json
import logging
import secrets
import string
from dataclasses import dataclass
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
from app.integrations.telegram.client import TelegramAPIError, TelegramClient
from app.integrations.telegram.db_models import (
    AgentTelegramBotDB,
    TelegramIdentityDB,
    TelegramToolDiscoveryMode,
    TelegramWorkspaceSettingsDB,
)
from app.integrations.telegram.repository import (
    AgentTelegramBotRepository,
    TelegramIdentityRepository,
    TelegramThreadBindingRepository,
    TelegramWorkspaceSettingsRepository,
)
from app.integrations.telegram.schemas import (
    TelegramBotResponse,
    TelegramBotUpdate,
    TelegramIdentityResponse,
    TelegramLinkCodeResponse,
    TelegramWorkspaceSettingsResponse,
)
from app.redis_client import get_redis
from app.utils.encryption import decrypt_value, encrypt_value
from app.workspaces.dependencies import get_active_workspace_id
from app.workspaces.repository import WorkspaceRepository


logger = logging.getLogger(__name__)
LINK_TTL_SECONDS = 600
LINK_PREFIX = "telegram:link:"


@dataclass(frozen=True)
class TelegramRuntimeConfig:
    id: UUID
    workspace_id: UUID
    agent_id: UUID
    workspace_enabled: bool
    enabled: bool
    require_mention_in_groups: bool
    show_tool_callouts: bool
    show_auxilia_link: bool
    tool_discovery_mode: TelegramToolDiscoveryMode
    bot_id: str
    bot_username: str | None
    bot_token: str
    webhook_secret: str


class TelegramWorkspaceSettingsService:
    def __init__(self, db: AsyncSession, workspace_id: UUID):
        self.db = db
        self.workspace_id = workspace_id
        self.repository = TelegramWorkspaceSettingsRepository(db)

    async def get_response(self) -> TelegramWorkspaceSettingsResponse:
        row = await self.repository.get_for_workspace(self.workspace_id)
        return TelegramWorkspaceSettingsResponse(enabled=bool(row and row.enabled))

    async def update(self, enabled: bool) -> TelegramWorkspaceSettingsResponse:
        row = await self.repository.get_for_workspace(self.workspace_id)
        if row is None:
            row = TelegramWorkspaceSettingsDB(
                workspace_id=self.workspace_id,
                enabled=enabled,
            )
        else:
            row.enabled = enabled
        self.db.add(row)
        await self.db.flush()
        return await self.get_response()


class TelegramBotService:
    def __init__(self, db: AsyncSession, workspace_id: UUID | None = None):
        self.db = db
        self.workspace_id = workspace_id
        self.repository = AgentTelegramBotRepository(db)
        self.workspace_settings = TelegramWorkspaceSettingsRepository(db)

    @staticmethod
    def _webhook_url(external_bot_id: str | None) -> str:
        suffix = external_bot_id or "BOT_ID"
        return (
            f"{auth_settings.FRONTEND_URL}/api/backend/integrations/telegram/"
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
        row: AgentTelegramBotDB | None,
        *,
        agent_id: UUID,
    ) -> TelegramBotResponse:
        return TelegramBotResponse(
            id=row.id if row else None,
            agent_id=agent_id,
            workspace_enabled=workspace_enabled,
            enabled=row.enabled if row else True,
            require_mention_in_groups=(row.require_mention_in_groups if row else True),
            show_tool_callouts=row.show_tool_callouts if row else True,
            show_auxilia_link=row.show_auxilia_link if row else True,
            tool_discovery_mode=(
                row.tool_discovery_mode
                if row
                else TelegramToolDiscoveryMode.all_capabilities
            ),
            is_configured=row is not None,
            bot_token_last4=(
                decrypt_value(row.bot_token_encrypted)[-4:] if row else None
            ),
            bot_id=row.bot_id if row else None,
            bot_username=row.bot_username if row else None,
            bot_name=row.bot_name if row else None,
            webhook_url=self._webhook_url(row.bot_id if row else None),
            deep_link_url=(
                f"https://t.me/{row.bot_username}" if row and row.bot_username else None
            ),
        )

    async def get_setup(self, agent_id: UUID) -> TelegramBotResponse:
        workspace_id = self._require_workspace()
        await self._ensure_agent(workspace_id, agent_id)
        return self._response(
            await self._workspace_enabled(workspace_id),
            None,
            agent_id=agent_id,
        )

    async def list_connections(self, agent_id: UUID) -> list[TelegramBotResponse]:
        workspace_id = self._require_workspace()
        await self._ensure_agent(workspace_id, agent_id)
        rows = await self.repository.list_for_agent(workspace_id, agent_id)
        enabled = await self._workspace_enabled(workspace_id)
        return [self._response(enabled, row, agent_id=agent_id) for row in rows]

    async def get_runtime(self, bot_id: UUID) -> TelegramRuntimeConfig | None:
        row = await self.repository.get(bot_id)
        if row is None:
            return None
        workspace_enabled = await self._workspace_enabled(row.workspace_id)
        return TelegramRuntimeConfig(
            id=row.id,
            workspace_id=row.workspace_id,
            agent_id=row.agent_id,
            workspace_enabled=workspace_enabled,
            enabled=row.enabled,
            require_mention_in_groups=row.require_mention_in_groups,
            show_tool_callouts=row.show_tool_callouts,
            show_auxilia_link=row.show_auxilia_link,
            tool_discovery_mode=row.tool_discovery_mode,
            bot_id=row.bot_id,
            bot_username=row.bot_username,
            bot_token=decrypt_value(row.bot_token_encrypted),
            webhook_secret=decrypt_value(row.webhook_secret_encrypted),
        )

    async def get_runtime_by_external_bot(
        self, external_bot_id: str
    ) -> TelegramRuntimeConfig | None:
        row = await self.repository.get_by_external_bot_id(external_bot_id)
        return await self.get_runtime(row.id) if row is not None else None

    async def create(
        self, agent_id: UUID, data: TelegramBotUpdate
    ) -> TelegramBotResponse:
        workspace_id = self._require_workspace()
        await self._ensure_agent(workspace_id, agent_id)
        token = (data.bot_token or "").strip()
        if not token:
            raise DomainValidationError("Telegram bot token is required")
        me = await self._validate_token(token)
        external_bot_id = str(me["id"])
        if await self.repository.get_by_external_bot_id(external_bot_id):
            raise AlreadyExistsError("This Telegram bot is already connected")
        secret = secrets.token_urlsafe(32)
        row = AgentTelegramBotDB(
            workspace_id=workspace_id,
            agent_id=agent_id,
            enabled=False,
            require_mention_in_groups=data.require_mention_in_groups,
            show_tool_callouts=data.show_tool_callouts,
            show_auxilia_link=data.show_auxilia_link,
            tool_discovery_mode=data.tool_discovery_mode,
            bot_id=external_bot_id,
            bot_username=str(me.get("username") or "") or None,
            bot_name=str(me.get("first_name") or "") or None,
            bot_token_encrypted=encrypt_value(token),
            webhook_secret_encrypted=encrypt_value(secret),
        )
        self.db.add(row)
        await self.db.flush()
        # Telegram's webhook is a non-rollbackable provider side effect. Persist
        # the disabled connection first so a failure remains safely retryable.
        await self.db.commit()
        if data.enabled:
            try:
                await TelegramClient(token).set_webhook(
                    self._webhook_url(external_bot_id), secret
                )
            except TelegramAPIError as exc:
                raise DomainValidationError(str(exc)) from None
            row.enabled = True
            self.db.add(row)
            await self.db.commit()
        await self.db.refresh(row)
        return self._response(
            await self._workspace_enabled(workspace_id),
            row,
            agent_id=agent_id,
        )

    async def update(
        self, agent_id: UUID, bot_id: UUID, data: TelegramBotUpdate
    ) -> TelegramBotResponse:
        workspace_id = self._require_workspace()
        row = await self.repository.get_for_scope(workspace_id, agent_id, bot_id)
        if row is None:
            raise NotFoundError("Telegram bot not found")
        current_token = decrypt_value(row.bot_token_encrypted)
        previous_bot_id = row.bot_id
        token = data.bot_token.strip() if data.bot_token is not None else current_token
        if not token:
            raise DomainValidationError("Telegram bot token cannot be empty")
        if data.bot_token is not None:
            me = await self._validate_token(token)
            external_bot_id = str(me["id"])
            existing = await self.repository.get_by_external_bot_id(external_bot_id)
            if existing is not None and existing.id != row.id:
                raise AlreadyExistsError("This Telegram bot is already connected")
            row.bot_id = external_bot_id
            row.bot_username = str(me.get("username") or "") or None
            row.bot_name = str(me.get("first_name") or "") or None
            row.bot_token_encrypted = encrypt_value(token)
        secret = decrypt_value(row.webhook_secret_encrypted)
        row.enabled = False
        row.require_mention_in_groups = data.require_mention_in_groups
        row.show_tool_callouts = data.show_tool_callouts
        row.show_auxilia_link = data.show_auxilia_link
        row.tool_discovery_mode = data.tool_discovery_mode
        self.db.add(row)
        await self.db.commit()
        if data.bot_token is not None and row.bot_id != previous_bot_id:
            try:
                await TelegramClient(current_token).delete_webhook()
            except TelegramAPIError:
                logger.warning(
                    "Previous Telegram webhook cleanup failed", exc_info=True
                )
        client = TelegramClient(token)
        try:
            if data.enabled:
                await client.set_webhook(self._webhook_url(row.bot_id), secret)
                row.enabled = True
                self.db.add(row)
                await self.db.commit()
            else:
                await client.delete_webhook()
        except TelegramAPIError as exc:
            raise DomainValidationError(str(exc)) from None
        await self.db.refresh(row)
        return self._response(
            await self._workspace_enabled(workspace_id),
            row,
            agent_id=agent_id,
        )

    async def delete(self, agent_id: UUID, bot_id: UUID) -> None:
        workspace_id = self._require_workspace()
        row = await self.repository.get_for_scope(workspace_id, agent_id, bot_id)
        if row is None:
            raise NotFoundError("Telegram bot not found")
        token = decrypt_value(row.bot_token_encrypted)
        await self.db.delete(row)
        # Commit the local deletion before the provider side effect. A failed
        # cleanup leaves no usable credential or route in Auxilia.
        await self.db.commit()
        try:
            await TelegramClient(token).delete_webhook()
        except TelegramAPIError:
            logger.warning("Telegram webhook cleanup failed", exc_info=True)

    async def _validate_token(self, token: str) -> dict:
        try:
            me = await TelegramClient(token).get_me()
        except TelegramAPIError as exc:
            raise DomainValidationError(
                "Could not validate Telegram bot token"
            ) from exc
        if not me.get("is_bot") or not me.get("id"):
            raise DomainValidationError("The Telegram token does not belong to a bot")
        return me

    def _require_workspace(self) -> UUID:
        if self.workspace_id is None:
            raise RuntimeError("A workspace is required for Telegram settings")
        return self.workspace_id


class TelegramIdentityService:
    def __init__(self, db: AsyncSession, workspace_id: UUID):
        self.db = db
        self.workspace_id = workspace_id
        self.repository = TelegramIdentityRepository(db)
        self.bindings = TelegramThreadBindingRepository(db)

    async def get_response(self, user_id: UUID) -> TelegramIdentityResponse:
        row = await self.repository.get_for_user(self.workspace_id, user_id)
        return TelegramIdentityResponse(
            linked=row is not None,
            username=row.username if row else None,
            display_name=row.display_name if row else None,
        )

    async def create_link_code(self, user_id: UUID) -> TelegramLinkCodeResponse:
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
            raise RuntimeError("Could not allocate a Telegram link code")
        bots = await AgentTelegramBotRepository(self.db).list_for_workspace(
            self.workspace_id
        )
        username = next((row.bot_username for row in bots if row.bot_username), None)
        return TelegramLinkCodeResponse(
            code=code,
            expires_in=LINK_TTL_SECONDS,
            deep_link_url=(
                f"https://t.me/{username}?start={code}" if username else None
            ),
        )

    async def consume_link_code(
        self,
        *,
        telegram_user_id: str,
        username: str | None,
        display_name: str | None,
        code: str,
    ) -> TelegramIdentityDB:
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
        existing_external = await self.repository.get_external(
            self.workspace_id, telegram_user_id
        )
        if existing_external is not None and existing_external.user_id != user_id:
            raise AlreadyExistsError("This Telegram account is already linked")
        previous = await self.repository.get_for_user(self.workspace_id, user_id)
        if previous is not None and previous.telegram_user_id != telegram_user_id:
            bots = await AgentTelegramBotRepository(self.db).list_for_workspace(
                self.workspace_id
            )
            await self.bindings.delete_for_identity(
                [bot.id for bot in bots], previous.telegram_user_id
            )
            await self.repository.unlink(self.workspace_id, user_id)
        row = existing_external or TelegramIdentityDB(
            workspace_id=self.workspace_id,
            telegram_user_id=telegram_user_id,
            user_id=user_id,
        )
        row.username = username
        row.display_name = display_name
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def unlink(self, user_id: UUID) -> None:
        identity = await self.repository.get_for_user(self.workspace_id, user_id)
        if identity is None:
            return
        bots = await AgentTelegramBotRepository(self.db).list_for_workspace(
            self.workspace_id
        )
        await self.bindings.delete_for_identity(
            [bot.id for bot in bots], identity.telegram_user_id
        )
        await self.repository.unlink(self.workspace_id, user_id)


def get_telegram_bot_service(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_active_workspace_id),
) -> TelegramBotService:
    return TelegramBotService(db, workspace_id)


def get_telegram_workspace_service(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_active_workspace_id),
) -> TelegramWorkspaceSettingsService:
    return TelegramWorkspaceSettingsService(db, workspace_id)
