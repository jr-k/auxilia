from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user, require_admin
from app.notifications.schemas import (
    NotificationChannelCreate,
    NotificationChannelPatch,
    NotificationChannelResponse,
    NotificationChannelTestResponse,
    SlackNotificationSettingsResponse,
    SlackNotificationSettingsUpdate,
)
from app.notifications.service import (
    NotificationChannelService,
    SlackNotificationSettingsService,
    get_notification_channel_service,
    get_slack_notification_settings_service,
)
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def list_notification_channels(
    user: UserDB = Depends(get_current_user),
    service: NotificationChannelService = Depends(get_notification_channel_service),
) -> list[NotificationChannelResponse]:
    return await service.list_channels(user.id)


@router.post("/channels", response_model=NotificationChannelResponse, status_code=201)
async def create_notification_channel(
    data: NotificationChannelCreate,
    user: UserDB = Depends(get_current_user),
    service: NotificationChannelService = Depends(get_notification_channel_service),
) -> NotificationChannelResponse:
    return await service.create(data, user.id)


@router.patch("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_notification_channel(
    channel_id: UUID,
    data: NotificationChannelPatch,
    user: UserDB = Depends(get_current_user),
    service: NotificationChannelService = Depends(get_notification_channel_service),
) -> NotificationChannelResponse:
    return await service.update(channel_id, data, user.id)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_notification_channel(
    channel_id: UUID,
    user: UserDB = Depends(get_current_user),
    service: NotificationChannelService = Depends(get_notification_channel_service),
) -> None:
    await service.delete(channel_id, user.id)


@router.post(
    "/channels/{channel_id}/test",
    response_model=NotificationChannelTestResponse,
)
async def test_notification_channel(
    channel_id: UUID,
    user: UserDB = Depends(get_current_user),
    service: NotificationChannelService = Depends(get_notification_channel_service),
) -> NotificationChannelTestResponse:
    return await service.test(channel_id, user.id)


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
