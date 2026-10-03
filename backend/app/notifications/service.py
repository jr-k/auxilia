from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.settings import auth_settings
from app.database import get_db
from app.exceptions import DomainValidationError
from app.notifications.repository import SlackNotificationSettingsRepository
from app.notifications.schemas import (
    SlackNotificationSettingsResponse,
    SlackNotificationSettingsUpdate,
)


@dataclass(frozen=True)
class SlackRuntimeConfig:
    bot_token: str
    signing_secret: str


class SlackNotificationSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SlackNotificationSettingsRepository(db)

    async def get_runtime_config(self) -> SlackRuntimeConfig | None:
        credentials = await self.repository.get_credentials()
        if credentials is None:
            return None
        return SlackRuntimeConfig(
            bot_token=credentials[0],
            signing_secret=credentials[1],
        )

    async def get_response(self) -> SlackNotificationSettingsResponse:
        row = await self.repository.get_settings()
        credentials = await self.repository.get_credentials()
        bot_token = credentials[0] if credentials else None
        base = f"{auth_settings.FRONTEND_URL}/api/backend/integrations/slack"
        return SlackNotificationSettingsResponse(
            enabled=bool(row and row.enabled),
            is_configured=credentials is not None,
            bot_token_last4=bot_token[-4:] if bot_token else None,
            bot_token_length=len(bot_token) if bot_token else None,
            has_signing_secret=credentials is not None,
            events_url=f"{base}/events",
            interactions_url=f"{base}/interactions",
        )

    async def update(
        self, data: SlackNotificationSettingsUpdate
    ) -> SlackNotificationSettingsResponse:
        existing = await self.repository.get_settings()
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
        if bot_token == "" or signing_secret == "":
            raise DomainValidationError("Slack credentials cannot be empty")
        if data.enabled and not has_existing_pair and bot_token is None:
            raise DomainValidationError("Slack credentials are required")
        await self.repository.save(
            enabled=data.enabled,
            bot_token=bot_token,
            signing_secret=signing_secret,
        )
        return await self.get_response()

    async def clear(self) -> SlackNotificationSettingsResponse:
        await self.repository.clear()
        return await self.get_response()


def get_slack_notification_settings_service(
    db: AsyncSession = Depends(get_db),
) -> SlackNotificationSettingsService:
    return SlackNotificationSettingsService(db)
