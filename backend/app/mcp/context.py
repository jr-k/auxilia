from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver import Context
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ROLE_HIERARCHY
from app.database import AsyncSessionLocal
from app.exceptions import (
    DomainValidationError,
    InvalidCredentialsError,
    PermissionDeniedError,
)
from app.users.models import UserDB, WorkspaceRole
from app.workspaces.repository import WorkspaceRepository


@asynccontextmanager
async def tool_session(
    _ctx: Context,
    *,
    minimum_role: WorkspaceRole | None = None,
) -> AsyncIterator[tuple[AsyncSession, UserDB, UUID]]:
    """Open one transaction and hydrate the OAuth grant's workspace identity."""
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        raise InvalidCredentialsError("A valid OAuth access token is required")
    claims = access_token.claims or {}
    workspace_value = claims.get("workspace_id")
    if not isinstance(workspace_value, str):
        raise InvalidCredentialsError("The OAuth token has no workspace")
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


def to_json(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", exclude_none=True)
    if isinstance(model, list):
        return [to_json(item) for item in model]
    return model
