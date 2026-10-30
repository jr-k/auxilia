from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.notifications.models import SlackNotificationSettingsDB
from app.repository import BaseRepository


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
    ) -> SlackNotificationSettingsDB:
        row = await self._get_or_create(workspace_id)
        row.enabled = enabled
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row
