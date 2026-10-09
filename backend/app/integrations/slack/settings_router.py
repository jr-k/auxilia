from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.agents.dependencies import require_agent_permission
from app.agents.models import EffectivePermission
from app.integrations.slack.schemas import AgentSlackBotResponse, AgentSlackBotUpdate
from app.integrations.slack.service import (
    AgentSlackBotService,
    get_agent_slack_bot_service,
)


router = APIRouter(prefix="/agents", tags=["agent-slack"])

_require_viewer = require_agent_permission(
    EffectivePermission.member, action="view this agent's Slack bot"
)
_require_admin = require_agent_permission(
    EffectivePermission.admin, action="configure this agent's Slack bot"
)


@router.get(
    "/{agent_id}/integrations/slack",
    response_model=list[AgentSlackBotResponse],
    dependencies=[Depends(_require_viewer)],
)
async def list_agent_slack_bots(
    agent_id: UUID,
    service: AgentSlackBotService = Depends(get_agent_slack_bot_service),
) -> list[AgentSlackBotResponse]:
    return await service.list_connections(agent_id)


@router.get(
    "/{agent_id}/integrations/slack/setup",
    response_model=AgentSlackBotResponse,
    dependencies=[Depends(_require_viewer)],
)
async def get_agent_slack_bot_setup(
    agent_id: UUID,
    service: AgentSlackBotService = Depends(get_agent_slack_bot_service),
) -> AgentSlackBotResponse:
    return await service.get_setup(agent_id)


@router.post(
    "/{agent_id}/integrations/slack",
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
    "/{agent_id}/integrations/slack/{bot_id}",
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
    "/{agent_id}/integrations/slack/{bot_id}",
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
