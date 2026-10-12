from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.realtime.service import WorkspaceRealtimeService
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


router = APIRouter(prefix="/workspace-events", tags=["realtime"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def get_realtime_service() -> WorkspaceRealtimeService:
    return WorkspaceRealtimeService()


@router.get("/")
async def stream_workspace_events(
    current_user: UserDB = Depends(get_current_user),
    workspace_id: UUID = Depends(get_active_workspace_id),
    service: WorkspaceRealtimeService = Depends(get_realtime_service),
    db: AsyncSession = Depends(get_db),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    # The dependency session has finished authenticating the connection. Do
    # not hold its pooled DB connection for the lifetime of this SSE response.
    await db.commit()
    return StreamingResponse(
        service.stream(
            workspace_id=workspace_id,
            user_id=current_user.id,
            last_event_id=last_event_id,
        ),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
