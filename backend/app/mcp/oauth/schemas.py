from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel

from app.workspaces.schemas import WorkspaceResponse


class MCPOAuthClientInfo(BaseModel):
    name: str
    uri: AnyHttpUrl | None = None
    logo_uri: AnyHttpUrl | None = None


class MCPOAuthAuthorizationResponse(BaseModel):
    client: MCPOAuthClientInfo
    scopes: list[str]
    expires_at: datetime
    workspaces: list[WorkspaceResponse]
    active_workspace_id: UUID | None = None


class MCPOAuthApproval(BaseModel):
    workspace_id: UUID


class MCPOAuthRedirectResponse(BaseModel):
    redirect_url: str
