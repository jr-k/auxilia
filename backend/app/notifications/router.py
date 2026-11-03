from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user, require_admin
from app.notifications.schemas import (
    SlackNotificationSettingsResponse,
    SlackNotificationSettingsUpdate,
    WebPushConfigResponse,
    WebPushSubscriptionDelete,
    WebPushSubscriptionResponse,
    WebPushSubscriptionUpsert,
)
from app.notifications.service import (
    SlackNotificationSettingsService,
    WebPushSubscriptionService,
    get_slack_notification_settings_service,
    get_web_push_subscription_service,
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


@router.get("/web-push", response_model=WebPushConfigResponse)
async def get_web_push_config(
    _: UserDB = Depends(get_current_user),
) -> WebPushConfigResponse:
    return WebPushSubscriptionService.config()


@router.put(
    "/web-push/subscriptions",
    response_model=WebPushSubscriptionResponse,
)
async def upsert_web_push_subscription(
    data: WebPushSubscriptionUpsert,
    current_user: UserDB = Depends(get_current_user),
    service: WebPushSubscriptionService = Depends(get_web_push_subscription_service),
) -> WebPushSubscriptionResponse:
    return await service.upsert(current_user.id, data)


@router.delete(
    "/web-push/subscriptions",
    response_model=WebPushSubscriptionResponse,
)
async def delete_web_push_subscription(
    data: WebPushSubscriptionDelete,
    current_user: UserDB = Depends(get_current_user),
    service: WebPushSubscriptionService = Depends(get_web_push_subscription_service),
) -> WebPushSubscriptionResponse:
    return await service.delete(current_user.id, data.endpoint)
