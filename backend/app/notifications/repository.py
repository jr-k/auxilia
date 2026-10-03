from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.notifications.models import SlackNotificationSettingsDB
from app.repository import BaseRepository
from app.utils.encryption import decrypt_value, encrypt_value


class SlackNotificationSettingsRepository(BaseRepository[SlackNotificationSettingsDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(SlackNotificationSettingsDB, db)

    async def get_settings(self) -> SlackNotificationSettingsDB | None:
        stmt = select(SlackNotificationSettingsDB).where(
            SlackNotificationSettingsDB.key == "default"
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_credentials(self) -> tuple[str, str] | None:
        row = await self.get_settings()
        if (
            row is None
            or not row.enabled
            or not row.bot_token_encrypted
            or not row.signing_secret_encrypted
        ):
            return None
        return (
            decrypt_value(row.bot_token_encrypted),
            decrypt_value(row.signing_secret_encrypted),
        )

    async def save(
        self,
        *,
        enabled: bool,
        bot_token: str | None,
        signing_secret: str | None,
    ) -> SlackNotificationSettingsDB:
        row = await self.get_settings()
        if row is None:
            row = SlackNotificationSettingsDB()
        row.enabled = enabled
        if bot_token is not None:
            row.bot_token_encrypted = encrypt_value(bot_token)
        if signing_secret is not None:
            row.signing_secret_encrypted = encrypt_value(signing_secret)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def clear(self) -> None:
        row = await self.get_settings()
        if row is not None:
            await self.db.delete(row)
        await self.db.flush()
