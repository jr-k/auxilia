from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response

from app.artifacts.router import content_disposition
from app.auth.dependencies import get_current_user
from app.threads.shares.schemas import (
    ConversationShareResponse,
    PublicConversationResponse,
)
from app.threads.shares.service import (
    ConversationShareService,
    get_conversation_share_service,
)
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


router = APIRouter(prefix="/threads/{thread_id}/share", tags=["conversation shares"])
public_router = APIRouter(prefix="/public/conversations", tags=["public conversations"])


@router.get("")
async def get_share(
    thread_id: str,
    workspace_id: UUID = Depends(get_active_workspace_id),
    user: UserDB = Depends(get_current_user),
    service: ConversationShareService = Depends(get_conversation_share_service),
) -> ConversationShareResponse | None:
    return await service.get(workspace_id, thread_id, user.id)


@router.post("")
async def create_share(
    thread_id: str,
    workspace_id: UUID = Depends(get_active_workspace_id),
    user: UserDB = Depends(get_current_user),
    service: ConversationShareService = Depends(get_conversation_share_service),
) -> ConversationShareResponse:
    return await service.create(workspace_id, thread_id, user.id)


@router.delete("", status_code=204)
async def delete_share(
    thread_id: str,
    workspace_id: UUID = Depends(get_active_workspace_id),
    user: UserDB = Depends(get_current_user),
    service: ConversationShareService = Depends(get_conversation_share_service),
) -> None:
    await service.delete(workspace_id, thread_id, user.id)


def _public_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


@public_router.get("/{share_id}")
async def public_conversation(
    share_id: UUID,
    response: Response,
    token: str = Header(default="", alias="X-Auxilia-Share-Token"),
    service: ConversationShareService = Depends(get_conversation_share_service),
) -> PublicConversationResponse:
    _public_headers(response)
    return await service.public_snapshot(share_id, token)


@public_router.get(
    "/{share_id}/artifacts/{artifact_id}/content",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def public_artifact_content(
    share_id: UUID,
    artifact_id: UUID,
    token: str = Header(default="", alias="X-Auxilia-Share-Token"),
    service: ConversationShareService = Depends(get_conversation_share_service),
) -> Response:
    row, data = await service.public_artifact(share_id, artifact_id, token)
    response = Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": content_disposition(row.filename),
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
    _public_headers(response)
    return response
