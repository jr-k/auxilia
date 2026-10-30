from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.notifications.repository import SlackNotificationSettingsRepository
from app.notifications.schemas import (
    SlackNotificationSettingsResponse,
    SlackNotificationSettingsUpdate,
)


class SlackNotificationSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SlackNotificationSettingsRepository(db)

    async def get_response(
        self, workspace_id: UUID
    ) -> SlackNotificationSettingsResponse:
        row = await self.repository.get_settings(workspace_id)
        return SlackNotificationSettingsResponse(enabled=bool(row and row.enabled))

    async def update(
        self, workspace_id: UUID, data: SlackNotificationSettingsUpdate
    ) -> SlackNotificationSettingsResponse:
        await self.repository.save(
            workspace_id=workspace_id,
            enabled=data.enabled,
        )
        return await self.get_response(workspace_id)


def get_slack_notification_settings_service(
    db: AsyncSession = Depends(get_db),
) -> SlackNotificationSettingsService:
    return SlackNotificationSettingsService(db)
