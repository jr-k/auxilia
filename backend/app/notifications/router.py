from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_admin
from app.notifications.schemas import (
    DiscordNotificationSettingsResponse,
    DiscordNotificationSettingsUpdate,
    SlackNotificationSettingsResponse,
    SlackNotificationSettingsUpdate,
    TelegramNotificationSettingsResponse,
    TelegramNotificationSettingsUpdate,
)
from app.notifications.service import (
    DiscordNotificationSettingsService,
    SlackNotificationSettingsService,
    TelegramNotificationSettingsService,
    get_discord_notification_settings_service,
    get_slack_notification_settings_service,
    get_telegram_notification_settings_service,
)
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/slack", response_model=SlackNotificationSettingsResponse)
async def get_slack_settings(
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: SlackNotificationSettingsService = Depends(
        get_slack_notification_settings_service
    ),
) -> SlackNotificationSettingsResponse:
    return await service.get_response(workspace_id)


@router.put("/slack", response_model=SlackNotificationSettingsResponse)
async def update_slack_settings(
    data: SlackNotificationSettingsUpdate,
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: SlackNotificationSettingsService = Depends(
        get_slack_notification_settings_service
    ),
) -> SlackNotificationSettingsResponse:
    return await service.update(workspace_id, data)


@router.delete("/slack", response_model=SlackNotificationSettingsResponse)
async def delete_slack_settings(
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: SlackNotificationSettingsService = Depends(
        get_slack_notification_settings_service
    ),
) -> SlackNotificationSettingsResponse:
    return await service.clear(workspace_id)


@router.get("/telegram", response_model=TelegramNotificationSettingsResponse)
async def get_telegram_settings(
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: TelegramNotificationSettingsService = Depends(
        get_telegram_notification_settings_service
    ),
) -> TelegramNotificationSettingsResponse:
    return await service.get_response(workspace_id)


@router.put("/telegram", response_model=TelegramNotificationSettingsResponse)
async def update_telegram_settings(
    data: TelegramNotificationSettingsUpdate,
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: TelegramNotificationSettingsService = Depends(
        get_telegram_notification_settings_service
    ),
) -> TelegramNotificationSettingsResponse:
    return await service.update(workspace_id, data)


@router.delete("/telegram", response_model=TelegramNotificationSettingsResponse)
async def delete_telegram_settings(
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: TelegramNotificationSettingsService = Depends(
        get_telegram_notification_settings_service
    ),
) -> TelegramNotificationSettingsResponse:
    return await service.clear(workspace_id)


@router.get("/discord", response_model=DiscordNotificationSettingsResponse)
async def get_discord_settings(
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: DiscordNotificationSettingsService = Depends(
        get_discord_notification_settings_service
    ),
) -> DiscordNotificationSettingsResponse:
    return await service.get_response(workspace_id)


@router.put("/discord", response_model=DiscordNotificationSettingsResponse)
async def update_discord_settings(
    data: DiscordNotificationSettingsUpdate,
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: DiscordNotificationSettingsService = Depends(
        get_discord_notification_settings_service
    ),
) -> DiscordNotificationSettingsResponse:
    return await service.update(workspace_id, data)


@router.delete("/discord", response_model=DiscordNotificationSettingsResponse)
async def delete_discord_settings(
    _: UserDB = Depends(require_admin),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: DiscordNotificationSettingsService = Depends(
        get_discord_notification_settings_service
    ),
) -> DiscordNotificationSettingsResponse:
    return await service.clear(workspace_id)
