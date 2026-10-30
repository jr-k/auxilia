import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import parse_qs
from uuid import UUID

import httpx
from fastapi import Header, HTTPException, Request
from slack_sdk.web.async_client import AsyncWebClient

from app.database import AsyncSessionLocal
from app.integrations.slack.db_models import SlackToolDiscoveryMode
from app.integrations.slack.models import SlackUserInfo
from app.users.models import UserDB
from app.users.repository import UserRepository
from app.workspaces.repository import WorkspaceRepository


logger = logging.getLogger(__name__)

_MAX_AGE_SECONDS = 60 * 5


@dataclass(frozen=True)
class VerifiedSlackRequest:
    body: bytes
    workspace_id: UUID
    team_id: str
    slack_bot_id: UUID
    agent_id: UUID
    integration_enabled: bool
    require_mention_in_threads: bool
    tool_discovery_mode: SlackToolDiscoveryMode


def _team_id(body: bytes) -> str | None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raw = parse_qs(body.decode()).get("payload", [None])[0]
        if raw is None:
            return None
        data = json.loads(raw)
    team = data.get("team")
    return data.get("team_id") or (team.get("id") if isinstance(team, dict) else None)


def _signature_matches(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected = (
        "v0="
        + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


async def verify_agent_slack_signature(
    agent_id: UUID,
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...),
) -> VerifiedSlackRequest:
    """Verify a callback against the Slack app installed for one agent."""
    timestamp = int(x_slack_request_timestamp)
    if abs(time.time() - timestamp) > _MAX_AGE_SECONDS:
        raise HTTPException(status_code=403, detail="Request too old")
    body = await request.body()
    team_id = _team_id(body)

    from app.integrations.slack.service import AgentSlackBotService

    async with AsyncSessionLocal() as db:
        configs = await AgentSlackBotService(db).list_for_verification(agent_id)
    candidates = [
        config
        for config in configs
        if team_id is None or config.slack_team_id == team_id
    ]
    if not candidates:
        raise HTTPException(status_code=403, detail="Slack bot is not configured")
    config = next(
        (
            candidate
            for candidate in candidates
            if _signature_matches(
                candidate.signing_secret,
                x_slack_request_timestamp,
                body,
                x_slack_signature,
            )
        ),
        None,
    )
    if config is None:
        raise HTTPException(status_code=403, detail="Invalid signature")

    return VerifiedSlackRequest(
        body=body,
        workspace_id=config.workspace_id,
        team_id=team_id or config.slack_team_id,
        slack_bot_id=config.id,
        agent_id=config.agent_id,
        integration_enabled=config.enabled and config.workspace_enabled,
        require_mention_in_threads=config.require_mention_in_threads,
        tool_discovery_mode=config.tool_discovery_mode,
    )


async def get_slack_client(
    workspace_id: UUID, slack_bot_id: UUID
) -> AsyncWebClient | None:
    from app.integrations.slack.service import AgentSlackBotService

    async with AsyncSessionLocal() as db:
        config = await AgentSlackBotService(db).get_runtime(slack_bot_id)
    if config is None or config.workspace_id != workspace_id:
        return None
    return AsyncWebClient(token=config.bot_token)


async def get_user_info(
    user_id: str, workspace_id: UUID, slack_bot_id: UUID
) -> SlackUserInfo | None:
    """Get user information from Slack API."""
    url = "https://slack.com/api/users.info"
    slack_client = await get_slack_client(workspace_id, slack_bot_id)
    if slack_client is None:
        return None
    headers = {"Authorization": f"Bearer {slack_client.token}"}
    params = {"user": user_id}

    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            if data.get("ok"):
                return SlackUserInfo.model_validate(data.get("user"))
            logger.warning("Slack API error (users.info): %s", data.get("error"))
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                "HTTP error calling Slack API (users.info): %s - %s",
                e.response.status_code,
                e.response.text,
            )
            return None
        except Exception:
            logger.exception("Unexpected error calling Slack API (users.info)")
            return None


async def resolve_user(
    slack_user_id: str,
    workspace_id: UUID,
    slack_bot_id: UUID,
) -> UserDB | None:
    """Map a Slack user ID to an internal user via email lookup."""
    user_info = await get_user_info(slack_user_id, workspace_id, slack_bot_id)
    if not user_info or not user_info.profile.email:
        return None
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email(user_info.profile.email)
        if user is None:
            return None
        membership = await WorkspaceRepository(db).get_membership(workspace_id, user.id)
        if membership is None:
            return None
        user.set_workspace_membership(membership)
        return user
