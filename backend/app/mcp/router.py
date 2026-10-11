"""auxilia's authenticated management MCP server."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context, MCPServer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.service import AgentService
from app.agents.schemas import AgentConfig
from app.auth.dependencies import ROLE_HIERARCHY, WORKSPACE_HEADER
from app.auth.tokens.repository import PersonalAccessTokenRepository
from app.auth.tokens.service import TOKEN_PREFIX
from app.database import AsyncSessionLocal
from app.exceptions import (
    DomainValidationError,
    InvalidCredentialsError,
    NotFoundError,
    PermissionDeniedError,
)
from app.mcp.servers.service import MCPServerService
from app.model_providers.service import ModelService
from app.pagination import PageParams
from app.runtime.api.protocol_service import ProtocolService
from app.settings import app_settings
from app.skills.schemas import SkillSave
from app.skills.service import SkillService
from app.threads.service import ThreadService
from app.users.models import UserDB, WorkspaceRole
from app.workspaces.repository import WorkspaceRepository


class AuxiliaTokenVerifier:
    """Authenticate MCP calls with the same PATs as the HTTP API."""

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token.startswith(TOKEN_PREFIX):
            return None
        async with AsyncSessionLocal() as db:
            pat = await PersonalAccessTokenRepository(db).get_by_token(token)
            if pat is None:
                return None
            return AccessToken(
                token=token,
                client_id=str(pat.id),
                subject=str(pat.user_id),
                scopes=["auxilia"],
            )


@asynccontextmanager
async def _tool_session(
    ctx: Context,
    *,
    minimum_role: WorkspaceRole | None = None,
) -> AsyncIterator[tuple[AsyncSession, UserDB, UUID]]:
    """Open one transaction and hydrate the PAT's workspace identity."""
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        raise InvalidCredentialsError("A valid personal access token is required")
    headers = ctx.headers or {}
    workspace_value = headers.get(WORKSPACE_HEADER)
    if workspace_value is None:
        raise DomainValidationError(f"{WORKSPACE_HEADER} is required")
    try:
        workspace_id = UUID(workspace_value)
        user_id = UUID(access_token.subject)
    except ValueError as exc:
        raise DomainValidationError("Invalid MCP identity or workspace") from exc

    async with AsyncSessionLocal() as db:
        try:
            user = await db.get(UserDB, user_id)
            if user is None:
                raise InvalidCredentialsError("The token owner no longer exists")
            membership = await WorkspaceRepository(db).get_membership(
                workspace_id, user.id
            )
            if membership is None:
                raise PermissionDeniedError("Workspace access denied")
            user.set_workspace_membership(membership)
            if (
                minimum_role is not None
                and ROLE_HIERARCHY[user.role] < ROLE_HIERARCHY[minimum_role]
            ):
                raise PermissionDeniedError(f"{minimum_role.value} access required")
            yield db, user, workspace_id
        except Exception:
            await db.rollback()
            raise
        else:
            await db.commit()


def _json(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", exclude_none=True)
    if isinstance(model, list):
        return [_json(item) for item in model]
    return model


auxilia_mcp = MCPServer(
    "Auxilia",
    description=(
        "Manage an Auxilia workspace: agents, skills, conversations, models, "
        "and MCP server bindings."
    ),
    token_verifier=AuxiliaTokenVerifier(),
    auth=AuthSettings(
        issuer_url=app_settings.backend_url,
        resource_server_url=None,
        required_scopes=["auxilia"],
    ),
)


@auxilia_mcp.tool()
async def list_skills(ctx: Context) -> list[dict[str, Any]]:
    """List skills visible in the selected workspace."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        return _json(await SkillService(db, workspace_id).list_summaries(user))


@auxilia_mcp.tool()
async def get_skill(skill_id: UUID, ctx: Context) -> dict[str, Any]:
    """Read one skill, including its SKILL.md content and metadata."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        return _json(await SkillService(db, workspace_id).get(skill_id, user))


@auxilia_mcp.tool()
async def create_skill(data: SkillSave, ctx: Context) -> dict[str, Any]:
    """Create a skill. The content must be a complete valid SKILL.md document."""
    async with _tool_session(ctx, minimum_role=WorkspaceRole.editor) as (
        db,
        user,
        workspace_id,
    ):
        return _json(await SkillService(db, workspace_id).create(data, user))


@auxilia_mcp.tool()
async def update_skill(skill_id: UUID, data: SkillSave, ctx: Context) -> dict[str, Any]:
    """Replace a skill using its current revision for optimistic concurrency."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        return _json(await SkillService(db, workspace_id).update(skill_id, data, user))


@auxilia_mcp.tool()
async def delete_skill(
    skill_id: UUID, ctx: Context, detach_agents: bool = False
) -> dict[str, bool]:
    """Delete a skill, optionally detaching it from every agent first."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        await SkillService(db, workspace_id).delete(
            skill_id, user, detach_agents=detach_agents
        )
        return {"deleted": True}


@auxilia_mcp.tool()
async def search_conversations(
    ctx: Context,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search the caller's conversations by title, first message, or agent name."""
    if not 1 <= limit <= 200 or offset < 0:
        raise DomainValidationError(
            "limit must be 1..200 and offset must be non-negative"
        )
    async with _tool_session(ctx) as (db, user, workspace_id):
        page = await ThreadService(db, workspace_id).list(
            user.id, PageParams(limit=limit, offset=offset), query=query
        )
        return _json(page)


@auxilia_mcp.tool()
async def get_conversation(thread_id: str, ctx: Context) -> dict[str, Any]:
    """Read one owned conversation and its current message snapshot."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        service = ThreadService(db, workspace_id)
        thread = await service.get(thread_id)
        if thread.user_id != user.id:
            raise NotFoundError("Thread not found")
        metadata = await service.get_with_agent(thread_id)
        state = await ProtocolService().thread_state(workspace_id, thread_id)
        return {"thread": _json(metadata), "state": state}


@auxilia_mcp.tool()
async def list_agents(ctx: Context, archived: bool = False) -> list[dict[str, Any]]:
    """List agents visible to the caller."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        agents = await AgentService(db, workspace_id).list(
            user_id=user.id,
            user_role=user.role,
            user_team_id=user.team_id,
            archived=archived,
        )
        return _json(
            [agent for agent in agents if agent.current_user_permission is not None]
        )


@auxilia_mcp.tool()
async def get_agent(agent_id: UUID, ctx: Context) -> dict[str, Any]:
    """Read an agent's complete configuration."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        return _json(
            await AgentService(db, workspace_id).get(
                agent_id,
                user_id=user.id,
                user_role=user.role,
                user_team_id=user.team_id,
            )
        )


@auxilia_mcp.tool()
async def create_agent(config: AgentConfig, ctx: Context) -> dict[str, Any]:
    """Create an agent with its complete skills, MCP, sandbox, and subagent config."""
    async with _tool_session(ctx, minimum_role=WorkspaceRole.editor) as (
        db,
        user,
        workspace_id,
    ):
        return _json(
            await AgentService(db, workspace_id).create_from_config(
                config,
                owner_id=user.id,
                user_role=user.role,
                user_team_id=user.team_id,
            )
        )


@auxilia_mcp.tool()
async def update_agent(
    agent_id: UUID, config: AgentConfig, ctx: Context
) -> dict[str, Any]:
    """Replace an agent's complete configuration atomically."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        return _json(
            await AgentService(db, workspace_id).set_config(
                agent_id,
                config,
                user_id=user.id,
                user_role=user.role,
                user_team_id=user.team_id,
            )
        )


@auxilia_mcp.tool()
async def archive_agent(agent_id: UUID, ctx: Context) -> dict[str, bool]:
    """Archive an agent."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        await AgentService(db, workspace_id).delete(
            agent_id, user_id=user.id, user_role=user.role
        )
        return {"archived": True}


@auxilia_mcp.tool()
async def restore_agent(agent_id: UUID, ctx: Context) -> dict[str, Any]:
    """Restore an archived agent."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        return _json(
            await AgentService(db, workspace_id).restore(
                agent_id,
                user_id=user.id,
                user_role=user.role,
                user_team_id=user.team_id,
            )
        )


@auxilia_mcp.tool()
async def list_mcp_servers(ctx: Context) -> list[dict[str, Any]]:
    """List MCP servers available for agent configuration."""
    async with _tool_session(ctx) as (db, user, workspace_id):
        return _json(await MCPServerService(db, workspace_id).list_responses(user))


@auxilia_mcp.tool()
async def list_models(ctx: Context) -> list[dict[str, Any]]:
    """List models currently available for agent defaults and conversations."""
    async with _tool_session(ctx) as (db, _user, workspace_id):
        return _json(await ModelService(db, workspace_id).list_available())
