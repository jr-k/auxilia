from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.notifications.models import (
    NotificationChannelDB,
    NotificationChannelType,
    SlackNotificationSettingsDB,
    TriggerNotificationDB,
)
from app.repository import BaseRepository
from app.utils.encryption import decrypt_value, encrypt_value


class NotificationChannelRepository(BaseRepository[NotificationChannelDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(NotificationChannelDB, db)

    async def list_for_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> list[NotificationChannelDB]:
        stmt = (
            select(NotificationChannelDB)
            .where(
                NotificationChannelDB.workspace_id == workspace_id,
                NotificationChannelDB.user_id == user_id,
            )
            .order_by(
                col(NotificationChannelDB.is_default).desc(),
                col(NotificationChannelDB.name),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_for_user(
        self, channel_id: UUID, workspace_id: UUID, user_id: UUID
    ) -> NotificationChannelDB | None:
        stmt = select(NotificationChannelDB).where(
            NotificationChannelDB.id == channel_id,
            NotificationChannelDB.workspace_id == workspace_id,
            NotificationChannelDB.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(
        self, workspace_id: UUID, user_id: UUID, name: str
    ) -> NotificationChannelDB | None:
        stmt = select(NotificationChannelDB).where(
            NotificationChannelDB.workspace_id == workspace_id,
            NotificationChannelDB.user_id == user_id,
            func.lower(NotificationChannelDB.name) == name.strip().lower(),
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_type(
        self,
        workspace_id: UUID,
        user_id: UUID,
        channel_type: NotificationChannelType,
    ) -> NotificationChannelDB | None:
        stmt = select(NotificationChannelDB).where(
            NotificationChannelDB.workspace_id == workspace_id,
            NotificationChannelDB.user_id == user_id,
            NotificationChannelDB.channel_type == channel_type,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_enabled_defaults(
        self, workspace_id: UUID, user_id: UUID
    ) -> list[NotificationChannelDB]:
        stmt = (
            select(NotificationChannelDB)
            .where(
                NotificationChannelDB.workspace_id == workspace_id,
                NotificationChannelDB.user_id == user_id,
                NotificationChannelDB.enabled,
                NotificationChannelDB.is_default,
            )
            .order_by(col(NotificationChannelDB.name))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_enabled_by_ids(
        self, workspace_id: UUID, user_id: UUID, channel_ids: list[UUID]
    ) -> list[NotificationChannelDB]:
        if not channel_ids:
            return []
        stmt = (
            select(NotificationChannelDB)
            .where(
                NotificationChannelDB.workspace_id == workspace_id,
                NotificationChannelDB.user_id == user_id,
                NotificationChannelDB.enabled,
                col(NotificationChannelDB.id).in_(channel_ids),
            )
            .order_by(col(NotificationChannelDB.name))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_enabled_by_names(
        self, workspace_id: UUID, user_id: UUID, names: list[str]
    ) -> list[NotificationChannelDB]:
        normalized = [name.strip().lower() for name in names if name.strip()]
        if not normalized:
            return []
        stmt = (
            select(NotificationChannelDB)
            .where(
                NotificationChannelDB.workspace_id == workspace_id,
                NotificationChannelDB.user_id == user_id,
                NotificationChannelDB.enabled,
                func.lower(NotificationChannelDB.name).in_(normalized),
            )
            .order_by(col(NotificationChannelDB.name))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class TriggerNotificationRepository(BaseRepository[TriggerNotificationDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(TriggerNotificationDB, db)

    async def get_for_trigger(self, trigger_id: UUID) -> TriggerNotificationDB | None:
        stmt = select(TriggerNotificationDB).where(
            TriggerNotificationDB.trigger_id == trigger_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_triggers(
        self, trigger_ids: list[UUID]
    ) -> dict[UUID, TriggerNotificationDB]:
        if not trigger_ids:
            return {}
        stmt = select(TriggerNotificationDB).where(
            col(TriggerNotificationDB.trigger_id).in_(trigger_ids)
        )
        result = await self.db.execute(stmt)
        return {row.trigger_id: row for row in result.scalars().all()}


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

    async def list_configured(self) -> list[SlackNotificationSettingsDB]:
        stmt = select(SlackNotificationSettingsDB).where(
            SlackNotificationSettingsDB.enabled,
            col(SlackNotificationSettingsDB.slack_team_id).is_not(None),
            col(SlackNotificationSettingsDB.bot_token_encrypted).is_not(None),
            col(SlackNotificationSettingsDB.signing_secret_encrypted).is_not(None),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

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
