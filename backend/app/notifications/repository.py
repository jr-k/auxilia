from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.notifications.models import (
    DiscordNotificationSettingsDB,
    SlackNotificationSettingsDB,
    TelegramNotificationSettingsDB,
)
from app.repository import BaseRepository
from app.utils.encryption import decrypt_value, encrypt_value


class SlackNotificationSettingsRepository(BaseRepository[SlackNotificationSettingsDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(SlackNotificationSettingsDB, db)

    async def get_settings(
        self, workspace_id: UUID | None = None
    ) -> SlackNotificationSettingsDB | None:
        stmt = select(SlackNotificationSettingsDB).where(
            SlackNotificationSettingsDB.key == "default"
        )
        if workspace_id is not None:
            stmt = stmt.where(SlackNotificationSettingsDB.workspace_id == workspace_id)
        else:
            stmt = stmt.limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_credentials(
        self, workspace_id: UUID | None = None
    ) -> tuple[str, str] | None:
        row = await self.get_settings(workspace_id)
        if (
            row is None
            or not row.bot_token_encrypted
            or not row.signing_secret_encrypted
        ):
            return None
        return (
            decrypt_value(row.bot_token_encrypted),
            decrypt_value(row.signing_secret_encrypted),
        )

    async def get_by_team_id(self, team_id: str) -> SlackNotificationSettingsDB | None:
        stmt = select(SlackNotificationSettingsDB).where(
            SlackNotificationSettingsDB.slack_team_id == team_id,
            SlackNotificationSettingsDB.enabled,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_or_create(self, workspace_id: UUID) -> SlackNotificationSettingsDB:
        row = await self.get_settings(workspace_id)
        if row is not None:
            return row
        try:
            async with self.db.begin_nested():
                row = SlackNotificationSettingsDB(workspace_id=workspace_id)
                self.db.add(row)
                await self.db.flush()
        except IntegrityError:
            row = await self.get_settings(workspace_id)
            if row is None:
                raise
        return row

    async def save(
        self,
        *,
        workspace_id: UUID,
        enabled: bool,
        bot_token: str | None,
        signing_secret: str | None,
        slack_team_id: str | None,
    ) -> SlackNotificationSettingsDB:
        row = await self._get_or_create(workspace_id)
        row.enabled = enabled
        row.slack_team_id = slack_team_id
        if bot_token is not None:
            row.bot_token_encrypted = encrypt_value(bot_token)
        if signing_secret is not None:
            row.signing_secret_encrypted = encrypt_value(signing_secret)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def clear(self, workspace_id: UUID) -> None:
        row = await self.get_settings(workspace_id)
        if row is not None:
            await self.db.delete(row)
        await self.db.flush()


class TelegramNotificationSettingsRepository(
    BaseRepository[TelegramNotificationSettingsDB]
):
    def __init__(self, db: AsyncSession):
        super().__init__(TelegramNotificationSettingsDB, db)

    async def get_settings(
        self, workspace_id: UUID
    ) -> TelegramNotificationSettingsDB | None:
        stmt = select(TelegramNotificationSettingsDB).where(
            TelegramNotificationSettingsDB.workspace_id == workspace_id,
            TelegramNotificationSettingsDB.key == "default",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_bot_id(self, bot_id: str) -> TelegramNotificationSettingsDB | None:
        stmt = select(TelegramNotificationSettingsDB).where(
            TelegramNotificationSettingsDB.bot_id == bot_id,
            TelegramNotificationSettingsDB.enabled,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_token(self, workspace_id: UUID) -> str | None:
        row = await self.get_settings(workspace_id)
        if row is None or not row.bot_token_encrypted:
            return None
        return decrypt_value(row.bot_token_encrypted)

    async def get_runtime_credentials(
        self, workspace_id: UUID
    ) -> tuple[str, str] | None:
        row = await self.get_settings(workspace_id)
        if (
            row is None
            or not row.enabled
            or (credentials := await self.get_credentials(workspace_id)) is None
        ):
            return None
        return credentials

    async def get_credentials(self, workspace_id: UUID) -> tuple[str, str] | None:
        row = await self.get_settings(workspace_id)
        if (
            row is None
            or not row.bot_token_encrypted
            or not row.webhook_secret_encrypted
        ):
            return None
        return (
            decrypt_value(row.bot_token_encrypted),
            decrypt_value(row.webhook_secret_encrypted),
        )

    async def _get_or_create(
        self, workspace_id: UUID
    ) -> TelegramNotificationSettingsDB:
        row = await self.get_settings(workspace_id)
        if row is not None:
            return row
        try:
            async with self.db.begin_nested():
                row = TelegramNotificationSettingsDB(workspace_id=workspace_id)
                self.db.add(row)
                await self.db.flush()
        except IntegrityError:
            row = await self.get_settings(workspace_id)
            if row is None:
                raise
        return row

    async def save(
        self,
        *,
        workspace_id: UUID,
        enabled: bool,
        bot_id: str,
        bot_username: str | None,
        bot_token: str | None,
        webhook_secret: str | None,
    ) -> TelegramNotificationSettingsDB:
        row = await self._get_or_create(workspace_id)
        row.enabled = enabled
        row.bot_id = bot_id
        row.bot_username = bot_username
        if bot_token is not None:
            row.bot_token_encrypted = encrypt_value(bot_token)
        if webhook_secret is not None:
            row.webhook_secret_encrypted = encrypt_value(webhook_secret)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def clear(self, workspace_id: UUID) -> None:
        row = await self.get_settings(workspace_id)
        if row is not None:
            await self.db.delete(row)
        await self.db.flush()


class DiscordNotificationSettingsRepository(
    BaseRepository[DiscordNotificationSettingsDB]
):
    def __init__(self, db: AsyncSession):
        super().__init__(DiscordNotificationSettingsDB, db)

    async def get_settings(
        self, workspace_id: UUID
    ) -> DiscordNotificationSettingsDB | None:
        stmt = select(DiscordNotificationSettingsDB).where(
            DiscordNotificationSettingsDB.workspace_id == workspace_id,
            DiscordNotificationSettingsDB.key == "default",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_application_id(
        self, application_id: str
    ) -> DiscordNotificationSettingsDB | None:
        stmt = select(DiscordNotificationSettingsDB).where(
            DiscordNotificationSettingsDB.application_id == application_id,
            DiscordNotificationSettingsDB.enabled,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_token(self, workspace_id: UUID) -> str | None:
        row = await self.get_settings(workspace_id)
        if row is None or not row.bot_token_encrypted:
            return None
        return decrypt_value(row.bot_token_encrypted)

    async def _get_or_create(self, workspace_id: UUID) -> DiscordNotificationSettingsDB:
        row = await self.get_settings(workspace_id)
        if row is not None:
            return row
        try:
            async with self.db.begin_nested():
                row = DiscordNotificationSettingsDB(workspace_id=workspace_id)
                self.db.add(row)
                await self.db.flush()
        except IntegrityError:
            row = await self.get_settings(workspace_id)
            if row is None:
                raise
        return row

    async def save(
        self,
        *,
        workspace_id: UUID,
        enabled: bool,
        application_id: str,
        public_key: str,
        bot_token: str | None,
        bot_user_id: str | None,
        bot_username: str | None,
    ) -> DiscordNotificationSettingsDB:
        row = await self._get_or_create(workspace_id)
        row.enabled = enabled
        row.application_id = application_id
        row.public_key = public_key
        row.bot_user_id = bot_user_id
        row.bot_username = bot_username
        if bot_token is not None:
            row.bot_token_encrypted = encrypt_value(bot_token)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def clear(self, workspace_id: UUID) -> None:
        row = await self.get_settings(workspace_id)
        if row is not None:
            await self.db.delete(row)
        await self.db.flush()
