from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.dependencies import require_agent_permission
from app.agents.models import EffectivePermission
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.integrations.slack.schemas import (
    AgentSlackBotResponse,
    AgentSlackBotUpdate,
    SlackIdentityResponse,
    SlackLinkCodeResponse,
)
from app.integrations.slack.service import (
    AgentSlackBotService,
    SlackIdentityService,
    get_agent_slack_bot_service,
)
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


router = APIRouter(tags=["slack"])

_require_viewer = require_agent_permission(
    EffectivePermission.member, action="view this agent's Slack bot"
)
_require_admin = require_agent_permission(
    EffectivePermission.admin, action="configure this agent's Slack bot"
)


@router.get(
    "/agents/{agent_id}/integrations/slack",
    response_model=list[AgentSlackBotResponse],
    dependencies=[Depends(_require_viewer)],
)
async def list_agent_slack_bots(
    agent_id: UUID,
    service: AgentSlackBotService = Depends(get_agent_slack_bot_service),
) -> list[AgentSlackBotResponse]:
    return await service.list_connections(agent_id)


@router.get(
    "/agents/{agent_id}/integrations/slack/setup",
    response_model=AgentSlackBotResponse,
    dependencies=[Depends(_require_viewer)],
)
async def get_agent_slack_bot_setup(
    agent_id: UUID,
    service: AgentSlackBotService = Depends(get_agent_slack_bot_service),
) -> AgentSlackBotResponse:
    return await service.get_setup(agent_id)


@router.post(
    "/agents/{agent_id}/integrations/slack",
    response_model=AgentSlackBotResponse,
    dependencies=[Depends(_require_admin)],
)
async def create_agent_slack_bot(
    agent_id: UUID,
    data: AgentSlackBotUpdate,
    service: AgentSlackBotService = Depends(get_agent_slack_bot_service),
) -> AgentSlackBotResponse:
    return await service.create(agent_id, data)


@router.put(
    "/agents/{agent_id}/integrations/slack/{bot_id}",
    response_model=AgentSlackBotResponse,
    dependencies=[Depends(_require_admin)],
)
async def update_agent_slack_bot(
    agent_id: UUID,
    bot_id: UUID,
    data: AgentSlackBotUpdate,
    service: AgentSlackBotService = Depends(get_agent_slack_bot_service),
) -> AgentSlackBotResponse:
    return await service.update(agent_id, bot_id, data)


@router.delete(
    "/agents/{agent_id}/integrations/slack/{bot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_require_admin)],
)
async def delete_agent_slack_bot(
    agent_id: UUID,
    bot_id: UUID,
    service: AgentSlackBotService = Depends(get_agent_slack_bot_service),
) -> Response:
    await service.delete(agent_id, bot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/integrations/slack/account",
    response_model=SlackIdentityResponse,
)
async def get_slack_account(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> SlackIdentityResponse:
    return await SlackIdentityService(db, workspace_id).get_response(current_user.id)


@router.post(
    "/integrations/slack/link-code",
    response_model=SlackLinkCodeResponse,
)
async def create_slack_link_code(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> SlackLinkCodeResponse:
    return await SlackIdentityService(db, workspace_id).create_link_code(
        current_user.id
    )


@router.delete(
    "/integrations/slack/account",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_slack_account(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await SlackIdentityService(db, workspace_id).unlink(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
