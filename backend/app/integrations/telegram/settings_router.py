from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.dependencies import require_agent_permission
from app.agents.models import EffectivePermission
from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.integrations.telegram.schemas import (
    TelegramBotResponse,
    TelegramBotUpdate,
    TelegramIdentityResponse,
    TelegramLinkCodeResponse,
    TelegramWorkspaceSettingsResponse,
    TelegramWorkspaceSettingsUpdate,
)
from app.integrations.telegram.service import (
    TelegramBotService,
    TelegramIdentityService,
    TelegramWorkspaceSettingsService,
    get_telegram_bot_service,
    get_telegram_workspace_service,
)
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


router = APIRouter(tags=["telegram"])

_require_viewer = require_agent_permission(
    EffectivePermission.member, action="view this agent's Telegram bot"
)
_require_agent_admin = require_agent_permission(
    EffectivePermission.admin, action="configure this agent's Telegram bot"
)


@router.get(
    "/notifications/telegram",
    response_model=TelegramWorkspaceSettingsResponse,
)
async def get_workspace_telegram_settings(
    _: UserDB = Depends(require_admin),
    service: TelegramWorkspaceSettingsService = Depends(get_telegram_workspace_service),
) -> TelegramWorkspaceSettingsResponse:
    return await service.get_response()


@router.put(
    "/notifications/telegram",
    response_model=TelegramWorkspaceSettingsResponse,
)
async def update_workspace_telegram_settings(
    data: TelegramWorkspaceSettingsUpdate,
    _: UserDB = Depends(require_admin),
    service: TelegramWorkspaceSettingsService = Depends(get_telegram_workspace_service),
) -> TelegramWorkspaceSettingsResponse:
    return await service.update(data.enabled)


@router.get(
    "/agents/{agent_id}/integrations/telegram",
    response_model=list[TelegramBotResponse],
    dependencies=[Depends(_require_viewer)],
)
async def list_agent_telegram_bots(
    agent_id: UUID,
    service: TelegramBotService = Depends(get_telegram_bot_service),
) -> list[TelegramBotResponse]:
    return await service.list_connections(agent_id)


@router.get(
    "/agents/{agent_id}/integrations/telegram/setup",
    response_model=TelegramBotResponse,
    dependencies=[Depends(_require_viewer)],
)
async def get_agent_telegram_setup(
    agent_id: UUID,
    service: TelegramBotService = Depends(get_telegram_bot_service),
) -> TelegramBotResponse:
    return await service.get_setup(agent_id)


@router.post(
    "/agents/{agent_id}/integrations/telegram",
    response_model=TelegramBotResponse,
    dependencies=[Depends(_require_agent_admin)],
)
async def create_agent_telegram_bot(
    agent_id: UUID,
    data: TelegramBotUpdate,
    service: TelegramBotService = Depends(get_telegram_bot_service),
) -> TelegramBotResponse:
    return await service.create(agent_id, data)


@router.put(
    "/agents/{agent_id}/integrations/telegram/{bot_id}",
    response_model=TelegramBotResponse,
    dependencies=[Depends(_require_agent_admin)],
)
async def update_agent_telegram_bot(
    agent_id: UUID,
    bot_id: UUID,
    data: TelegramBotUpdate,
    service: TelegramBotService = Depends(get_telegram_bot_service),
) -> TelegramBotResponse:
    return await service.update(agent_id, bot_id, data)


@router.delete(
    "/agents/{agent_id}/integrations/telegram/{bot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_require_agent_admin)],
)
async def delete_agent_telegram_bot(
    agent_id: UUID,
    bot_id: UUID,
    service: TelegramBotService = Depends(get_telegram_bot_service),
) -> Response:
    await service.delete(agent_id, bot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/integrations/telegram/account",
    response_model=TelegramIdentityResponse,
)
async def get_telegram_account(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> TelegramIdentityResponse:
    return await TelegramIdentityService(db, workspace_id).get_response(current_user.id)


@router.post(
    "/integrations/telegram/link-code",
    response_model=TelegramLinkCodeResponse,
)
async def create_telegram_link_code(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> TelegramLinkCodeResponse:
    return await TelegramIdentityService(db, workspace_id).create_link_code(
        current_user.id
    )


@router.delete(
    "/integrations/telegram/account",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_telegram_account(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await TelegramIdentityService(db, workspace_id).unlink(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
