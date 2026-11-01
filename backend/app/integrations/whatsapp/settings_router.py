from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.dependencies import require_agent_permission
from app.agents.models import EffectivePermission
from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.integrations.whatsapp.schemas import (
    WhatsAppConnectionResponse,
    WhatsAppConnectionUpdate,
    WhatsAppIdentityResponse,
    WhatsAppLinkCodeResponse,
    WhatsAppWorkspaceSettingsResponse,
    WhatsAppWorkspaceSettingsUpdate,
)
from app.integrations.whatsapp.service import (
    WhatsAppConnectionService,
    WhatsAppIdentityService,
    WhatsAppWorkspaceSettingsService,
    get_whatsapp_connection_service,
    get_whatsapp_workspace_service,
)
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


router = APIRouter(tags=["whatsapp"])
_require_viewer = require_agent_permission(
    EffectivePermission.member, action="view this agent's WhatsApp connection"
)
_require_agent_admin = require_agent_permission(
    EffectivePermission.admin, action="configure this agent's WhatsApp connection"
)


@router.get("/notifications/whatsapp", response_model=WhatsAppWorkspaceSettingsResponse)
async def get_workspace_whatsapp_settings(
    _: UserDB = Depends(require_admin),
    service: WhatsAppWorkspaceSettingsService = Depends(get_whatsapp_workspace_service),
) -> WhatsAppWorkspaceSettingsResponse:
    return await service.get_response()


@router.put("/notifications/whatsapp", response_model=WhatsAppWorkspaceSettingsResponse)
async def update_workspace_whatsapp_settings(
    data: WhatsAppWorkspaceSettingsUpdate,
    _: UserDB = Depends(require_admin),
    service: WhatsAppWorkspaceSettingsService = Depends(get_whatsapp_workspace_service),
) -> WhatsAppWorkspaceSettingsResponse:
    return await service.update(data.enabled)


@router.get(
    "/agents/{agent_id}/integrations/whatsapp",
    response_model=list[WhatsAppConnectionResponse],
    dependencies=[Depends(_require_viewer)],
)
async def list_agent_whatsapp_connections(
    agent_id: UUID,
    service: WhatsAppConnectionService = Depends(get_whatsapp_connection_service),
) -> list[WhatsAppConnectionResponse]:
    return await service.list_connections(agent_id)


@router.get(
    "/agents/{agent_id}/integrations/whatsapp/setup",
    response_model=WhatsAppConnectionResponse,
    dependencies=[Depends(_require_viewer)],
)
async def get_agent_whatsapp_setup(
    agent_id: UUID,
    service: WhatsAppConnectionService = Depends(get_whatsapp_connection_service),
) -> WhatsAppConnectionResponse:
    return await service.get_setup(agent_id)


@router.post(
    "/agents/{agent_id}/integrations/whatsapp",
    response_model=WhatsAppConnectionResponse,
    dependencies=[Depends(_require_agent_admin)],
)
async def create_agent_whatsapp_connection(
    agent_id: UUID,
    data: WhatsAppConnectionUpdate,
    service: WhatsAppConnectionService = Depends(get_whatsapp_connection_service),
) -> WhatsAppConnectionResponse:
    return await service.create(agent_id, data)


@router.put(
    "/agents/{agent_id}/integrations/whatsapp/{connection_id}",
    response_model=WhatsAppConnectionResponse,
    dependencies=[Depends(_require_agent_admin)],
)
async def update_agent_whatsapp_connection(
    agent_id: UUID,
    connection_id: UUID,
    data: WhatsAppConnectionUpdate,
    service: WhatsAppConnectionService = Depends(get_whatsapp_connection_service),
) -> WhatsAppConnectionResponse:
    return await service.update(agent_id, connection_id, data)


@router.delete(
    "/agents/{agent_id}/integrations/whatsapp/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_require_agent_admin)],
)
async def delete_agent_whatsapp_connection(
    agent_id: UUID,
    connection_id: UUID,
    service: WhatsAppConnectionService = Depends(get_whatsapp_connection_service),
) -> Response:
    await service.delete(agent_id, connection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/integrations/whatsapp/account", response_model=WhatsAppIdentityResponse)
async def get_whatsapp_account(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> WhatsAppIdentityResponse:
    return await WhatsAppIdentityService(db, workspace_id).get_response(current_user.id)


@router.post(
    "/integrations/whatsapp/link-code", response_model=WhatsAppLinkCodeResponse
)
async def create_whatsapp_link_code(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> WhatsAppLinkCodeResponse:
    return await WhatsAppIdentityService(db, workspace_id).create_link_code(
        current_user.id
    )


@router.delete("/integrations/whatsapp/account", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_whatsapp_account(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await WhatsAppIdentityService(db, workspace_id).unlink(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
