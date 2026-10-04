from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.integrations.channels.service import LINK_TTL_SECONDS, ChannelService
from app.notifications.models import ExternalProvider
from app.notifications.schemas import ExternalIdentityResponse, LinkCodeResponse
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


router = APIRouter(prefix="/integrations/channels", tags=["integrations"])


@router.post("/link-code", response_model=LinkCodeResponse)
async def create_link_code(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> LinkCodeResponse:
    code = await ChannelService(db).create_link_code(workspace_id, current_user.id)
    return LinkCodeResponse(code=code, expires_in=LINK_TTL_SECONDS)


@router.get("/identities", response_model=list[ExternalIdentityResponse])
async def list_identities(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> list[ExternalIdentityResponse]:
    rows = await ChannelService(db).identities.list_for_user(
        workspace_id, current_user.id
    )
    return [
        ExternalIdentityResponse(
            provider=row.provider.value,
            display_name=row.display_name,
        )
        for row in rows
    ]


@router.delete(
    "/identities/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_identity(
    provider: ExternalProvider,
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ChannelService(db).unlink_identity(workspace_id, provider, current_user.id)
