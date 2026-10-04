import logging
import secrets
from dataclasses import dataclass
from uuid import UUID

import httpx
from fastapi import Depends
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.settings import auth_settings
from app.database import get_db
from app.exceptions import DomainValidationError
from app.integrations.discord.client import DiscordClient
from app.integrations.telegram.client import TelegramClient
from app.notifications.repository import (
    DiscordNotificationSettingsRepository,
    SlackNotificationSettingsRepository,
    TelegramNotificationSettingsRepository,
)
from app.notifications.schemas import (
    DiscordNotificationSettingsResponse,
    DiscordNotificationSettingsUpdate,
    SlackNotificationSettingsResponse,
    SlackNotificationSettingsUpdate,
    TelegramNotificationSettingsResponse,
    TelegramNotificationSettingsUpdate,
)
from app.redis_client import get_redis


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlackRuntimeConfig:
    workspace_id: UUID
    slack_team_id: str
    bot_token: str
    signing_secret: str


class SlackNotificationSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SlackNotificationSettingsRepository(db)

    async def get_runtime_config(self, workspace_id: UUID) -> SlackRuntimeConfig | None:
        row = await self.repository.get_settings(workspace_id)
        credentials = await self.repository.get_credentials(workspace_id)
        if (
            credentials is None
            or row is None
            or not row.enabled
            or not row.slack_team_id
        ):
            return None
        return SlackRuntimeConfig(
            workspace_id=workspace_id,
            slack_team_id=row.slack_team_id,
            bot_token=credentials[0],
            signing_secret=credentials[1],
        )

    async def get_runtime_config_for_team(
        self, team_id: str
    ) -> SlackRuntimeConfig | None:
        row = await self.repository.get_by_team_id(team_id)
        if row is None:
            return None
        return await self.get_runtime_config(row.workspace_id)

    async def get_response(
        self, workspace_id: UUID
    ) -> SlackNotificationSettingsResponse:
        row = await self.repository.get_settings(workspace_id)
        credentials = await self.repository.get_credentials(workspace_id)
        bot_token = credentials[0] if credentials else None
        base = f"{auth_settings.FRONTEND_URL}/api/backend/integrations/slack"
        return SlackNotificationSettingsResponse(
            enabled=bool(row and row.enabled),
            is_configured=credentials is not None,
            bot_token_last4=bot_token[-4:] if bot_token else None,
            bot_token_length=len(bot_token) if bot_token else None,
            has_signing_secret=credentials is not None,
            slack_team_id=row.slack_team_id if row else None,
            events_url=f"{base}/events",
            interactions_url=f"{base}/interactions",
        )

    async def update(
        self, workspace_id: UUID, data: SlackNotificationSettingsUpdate
    ) -> SlackNotificationSettingsResponse:
        existing = await self.repository.get_settings(workspace_id)
        has_existing_pair = bool(
            existing
            and existing.bot_token_encrypted
            and existing.signing_secret_encrypted
        )
        bot_token = data.bot_token.strip() if data.bot_token is not None else None
        signing_secret = (
            data.signing_secret.strip() if data.signing_secret is not None else None
        )
        if (bot_token is None) != (signing_secret is None):
            raise DomainValidationError(
                "Slack bot token and signing secret must be updated together"
            )
        if bot_token is not None and not bot_token:
            raise DomainValidationError("Slack credentials cannot be empty")
        if signing_secret is not None and not signing_secret:
            raise DomainValidationError("Slack credentials cannot be empty")
        if data.enabled and not has_existing_pair and bot_token is None:
            raise DomainValidationError("Slack credentials are required")
        slack_team_id = (
            data.slack_team_id.strip()
            if data.slack_team_id is not None
            else existing.slack_team_id
            if existing
            else None
        )
        if bot_token is not None and not slack_team_id:
            try:
                auth = await AsyncWebClient(token=bot_token).auth_test()
                resolved_team_id = auth.get("team_id")
            except Exception as exc:
                raise DomainValidationError(
                    "Could not resolve the Slack workspace from the bot token"
                ) from exc
            if not isinstance(resolved_team_id, str) or not resolved_team_id:
                raise DomainValidationError(
                    "Slack did not return a workspace id for this bot token"
                )
            slack_team_id = resolved_team_id
        await self.repository.save(
            workspace_id=workspace_id,
            enabled=data.enabled,
            bot_token=bot_token,
            signing_secret=signing_secret,
            slack_team_id=slack_team_id,
        )
        return await self.get_response(workspace_id)

    async def clear(self, workspace_id: UUID) -> SlackNotificationSettingsResponse:
        await self.repository.clear(workspace_id)
        return await self.get_response(workspace_id)


def get_slack_notification_settings_service(
    db: AsyncSession = Depends(get_db),
) -> SlackNotificationSettingsService:
    return SlackNotificationSettingsService(db)


@dataclass(frozen=True)
class TelegramRuntimeConfig:
    workspace_id: UUID
    bot_id: str
    bot_token: str
    webhook_secret: str


class TelegramNotificationSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = TelegramNotificationSettingsRepository(db)

    async def get_runtime_config(
        self, workspace_id: UUID
    ) -> TelegramRuntimeConfig | None:
        row = await self.repository.get_settings(workspace_id)
        credentials = await self.repository.get_runtime_credentials(workspace_id)
        if row is None or not row.bot_id or credentials is None:
            return None
        return TelegramRuntimeConfig(
            workspace_id=workspace_id,
            bot_id=row.bot_id,
            bot_token=credentials[0],
            webhook_secret=credentials[1],
        )

    async def get_response(
        self, workspace_id: UUID
    ) -> TelegramNotificationSettingsResponse:
        row = await self.repository.get_settings(workspace_id)
        credentials = await self.repository.get_credentials(workspace_id)
        token = credentials[0] if credentials else None
        bot_id = row.bot_id if row else None
        base = f"{auth_settings.FRONTEND_URL}/api/backend/integrations/telegram"
        return TelegramNotificationSettingsResponse(
            enabled=bool(row and row.enabled),
            is_configured=credentials is not None and bool(bot_id),
            bot_token_last4=token[-4:] if token else None,
            bot_username=row.bot_username if row else None,
            webhook_url=f"{base}/{bot_id}/webhook"
            if bot_id
            else f"{base}/BOT_ID/webhook",
        )

    async def update(
        self, workspace_id: UUID, data: TelegramNotificationSettingsUpdate
    ) -> TelegramNotificationSettingsResponse:
        lock = get_redis().lock(
            f"integration-config:telegram:{workspace_id}",
            timeout=120,
            blocking_timeout=15,
        )
        if not await lock.acquire():
            raise DomainValidationError(
                "Telegram configuration is already being updated"
            )
        try:
            return await self._update_locked(workspace_id, data)
        finally:
            await lock.release()

    async def _update_locked(
        self, workspace_id: UUID, data: TelegramNotificationSettingsUpdate
    ) -> TelegramNotificationSettingsResponse:
        existing = await self.repository.get_settings(workspace_id)
        credentials = await self.repository.get_credentials(workspace_id)
        new_token = data.bot_token.strip() if data.bot_token is not None else None
        if new_token == "":
            raise DomainValidationError("Telegram bot token cannot be empty")
        token = new_token or (credentials[0] if credentials else None)
        if data.enabled and token is None:
            raise DomainValidationError("Telegram bot token is required")
        if token is None:
            raise DomainValidationError("Configure Telegram before changing its state")
        client = TelegramClient(token)
        if new_token is not None or existing is None or not existing.bot_id:
            me = await client.get_me()
            bot_id = str(me.get("id") or "")
            if not bot_id or not me.get("is_bot"):
                raise DomainValidationError(
                    "The Telegram token does not belong to a bot"
                )
            bot_username = (
                str(me["username"]) if isinstance(me.get("username"), str) else None
            )
        else:
            bot_id = existing.bot_id
            bot_username = existing.bot_username
        secret = credentials[1] if credentials else secrets.token_urlsafe(32)
        webhook_url = (
            f"{auth_settings.FRONTEND_URL}/api/backend/integrations/telegram/"
            f"{bot_id}/webhook"
        )
        await self.repository.save(
            workspace_id=workspace_id,
            enabled=False,
            bot_id=bot_id,
            bot_username=bot_username,
            bot_token=new_token,
            webhook_secret=secret if credentials is None else None,
        )
        # Persist the exact credentials/secret before telling Telegram to use
        # them. This is an intentional early commit before a non-rollbackable
        # provider side effect.
        await self.db.commit()
        if data.enabled:
            await client.set_webhook(webhook_url, secret)
            await self.repository.save(
                workspace_id=workspace_id,
                enabled=True,
                bot_id=bot_id,
                bot_username=bot_username,
                bot_token=None,
                webhook_secret=None,
            )
            await self.db.commit()
        else:
            try:
                await client.delete_webhook()
            except (DomainValidationError, httpx.HTTPError):
                logger.warning(
                    "Telegram webhook cleanup failed while disabling workspace %s",
                    workspace_id,
                    exc_info=True,
                )
        return await self.get_response(workspace_id)

    async def clear(self, workspace_id: UUID) -> TelegramNotificationSettingsResponse:
        lock = get_redis().lock(
            f"integration-config:telegram:{workspace_id}",
            timeout=120,
            blocking_timeout=15,
        )
        if not await lock.acquire():
            raise DomainValidationError(
                "Telegram configuration is already being updated"
            )
        try:
            token = await self.repository.get_token(workspace_id)
            await self.repository.clear(workspace_id)
            await self.db.commit()
            if token:
                try:
                    await TelegramClient(token).delete_webhook()
                except (DomainValidationError, httpx.HTTPError):
                    logger.warning(
                        "Telegram webhook cleanup failed while clearing workspace %s",
                        workspace_id,
                        exc_info=True,
                    )
            return await self.get_response(workspace_id)
        finally:
            await lock.release()


class DiscordNotificationSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = DiscordNotificationSettingsRepository(db)

    async def get_runtime_config(
        self, workspace_id: UUID
    ) -> "DiscordRuntimeConfig | None":
        row = await self.repository.get_settings(workspace_id)
        token = await self.repository.get_token(workspace_id)
        if (
            row is None
            or not row.enabled
            or not row.application_id
            or not row.public_key
            or not token
        ):
            return None
        return DiscordRuntimeConfig(
            workspace_id=workspace_id,
            application_id=row.application_id,
            public_key=row.public_key,
            bot_token=token,
        )

    async def get_response(
        self, workspace_id: UUID
    ) -> DiscordNotificationSettingsResponse:
        row = await self.repository.get_settings(workspace_id)
        token = await self.repository.get_token(workspace_id)
        application_id = row.application_id if row else None
        base = f"{auth_settings.FRONTEND_URL}/api/backend/integrations/discord"
        install_url = (
            "https://discord.com/oauth2/authorize"
            f"?client_id={application_id}&scope=bot%20applications.commands"
            "&permissions=277025459200"
            if application_id
            else None
        )
        return DiscordNotificationSettingsResponse(
            enabled=bool(row and row.enabled),
            is_configured=bool(token and application_id and row and row.public_key),
            bot_token_last4=token[-4:] if token else None,
            bot_username=row.bot_username if row else None,
            application_id=application_id,
            interactions_url=f"{base}/interactions",
            install_url=install_url,
        )

    async def update(
        self, workspace_id: UUID, data: DiscordNotificationSettingsUpdate
    ) -> DiscordNotificationSettingsResponse:
        lock = get_redis().lock(
            f"integration-config:discord:{workspace_id}",
            timeout=120,
            blocking_timeout=15,
        )
        if not await lock.acquire():
            raise DomainValidationError(
                "Discord configuration is already being updated"
            )
        try:
            return await self._update_locked(workspace_id, data)
        finally:
            await lock.release()

    async def _update_locked(
        self, workspace_id: UUID, data: DiscordNotificationSettingsUpdate
    ) -> DiscordNotificationSettingsResponse:
        existing = await self.repository.get_settings(workspace_id)
        new_token = data.bot_token.strip() if data.bot_token is not None else None
        if new_token == "":
            raise DomainValidationError("Discord bot token cannot be empty")
        token = new_token or await self.repository.get_token(workspace_id)
        application_id = (
            data.application_id.strip()
            if data.application_id is not None
            else existing.application_id
            if existing
            else None
        )
        public_key = (
            data.public_key.strip().lower()
            if data.public_key is not None
            else existing.public_key
            if existing
            else None
        )
        if data.enabled and not token:
            raise DomainValidationError("Discord bot token is required")
        if data.enabled and not application_id:
            raise DomainValidationError("Discord application id is required")
        if data.enabled and not public_key:
            raise DomainValidationError("Discord public key is required")
        try:
            if public_key and len(bytes.fromhex(public_key)) != 32:
                raise ValueError
        except ValueError as exc:
            raise DomainValidationError(
                "Discord public key must be 64 hexadecimal characters"
            ) from exc
        if token is None or application_id is None or public_key is None:
            raise DomainValidationError("Configure Discord before changing its state")
        client = DiscordClient(token)
        if data.enabled or new_token is not None:
            me = await client.get_me()
            if not me.get("bot"):
                raise DomainValidationError(
                    "The Discord token does not belong to a bot"
                )
        else:
            me = {
                "id": existing.bot_user_id if existing else None,
                "username": existing.bot_username if existing else None,
            }
        await self.repository.save(
            workspace_id=workspace_id,
            enabled=False,
            application_id=application_id,
            public_key=public_key,
            bot_token=new_token,
            bot_user_id=str(me.get("id") or "") or None,
            bot_username=str(me.get("username") or "") or None,
        )
        # Persist validated credentials before registering commands. If the
        # provider call fails, the integration remains configured but disabled.
        await self.db.commit()
        if data.enabled:
            await client.register_commands(application_id)
            await self.repository.save(
                workspace_id=workspace_id,
                enabled=True,
                application_id=application_id,
                public_key=public_key,
                bot_token=None,
                bot_user_id=str(me.get("id") or "") or None,
                bot_username=str(me.get("username") or "") or None,
            )
            await self.db.commit()
        return await self.get_response(workspace_id)

    async def clear(self, workspace_id: UUID) -> DiscordNotificationSettingsResponse:
        lock = get_redis().lock(
            f"integration-config:discord:{workspace_id}",
            timeout=120,
            blocking_timeout=15,
        )
        if not await lock.acquire():
            raise DomainValidationError(
                "Discord configuration is already being updated"
            )
        try:
            await self.repository.clear(workspace_id)
            await self.db.commit()
            return await self.get_response(workspace_id)
        finally:
            await lock.release()


def get_telegram_notification_settings_service(
    db: AsyncSession = Depends(get_db),
) -> TelegramNotificationSettingsService:
    return TelegramNotificationSettingsService(db)


def get_discord_notification_settings_service(
    db: AsyncSession = Depends(get_db),
) -> DiscordNotificationSettingsService:
    return DiscordNotificationSettingsService(db)


@dataclass(frozen=True)
class DiscordRuntimeConfig:
    workspace_id: UUID
    application_id: str
    public_key: str
    bot_token: str
