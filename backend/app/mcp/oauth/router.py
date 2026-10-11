from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.mcp.oauth.schemas import (
    MCPOAuthApproval,
    MCPOAuthAuthorizationResponse,
    MCPOAuthRedirectResponse,
)
from app.mcp.oauth.service import MCPOAuthService
from app.users.models import UserDB


router = APIRouter(prefix="/mcp/oauth/authorizations", tags=["mcp-oauth"])


def _secure(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"


@router.get("/{handle}", response_model=MCPOAuthAuthorizationResponse)
async def get_authorization(
    handle: str,
    response: Response,
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MCPOAuthAuthorizationResponse:
    _secure(response)
    return await MCPOAuthService(db).authorization_details(handle, user)


@router.post("/{handle}/approve", response_model=MCPOAuthRedirectResponse)
async def approve_authorization(
    handle: str,
    approval: MCPOAuthApproval,
    response: Response,
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MCPOAuthRedirectResponse:
    _secure(response)
    return await MCPOAuthService(db).approve(handle, approval.workspace_id, user)


@router.post("/{handle}/deny", response_model=MCPOAuthRedirectResponse)
async def deny_authorization(
    handle: str,
    response: Response,
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MCPOAuthRedirectResponse:
    _secure(response)
    return await MCPOAuthService(db).deny(handle, user)
