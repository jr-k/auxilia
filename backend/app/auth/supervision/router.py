from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import (
    SupervisionContext,
    detect_auth_method,
    get_supervision_context,
    require_instance_owner,
)
from app.auth.supervision.schemas import SupervisionStartRequest
from app.auth.supervision.service import (
    SupervisionService,
    get_supervision_service,
)
from app.auth.utils import (
    SessionClaims,
    attach_auth_cookie,
    create_access_token,
)
from app.exceptions import DomainValidationError, PermissionDeniedError
from app.users.models import UserDB
from app.users.schemas import CurrentUserResponse, SupervisionInfo
from app.workspaces.cookies import (
    clear_active_workspace_cookie,
    set_active_workspace_cookie,
)


router = APIRouter(prefix="/auth/supervision", tags=["auth"])


def _response(
    user: UserDB,
    token: str,
    *,
    supervision: SupervisionInfo | None,
) -> JSONResponse:
    payload = CurrentUserResponse.model_validate(
        user,
        update={
            "workspace_id": user.active_workspace_id,
            "supervision": supervision,
        },
    )
    response = JSONResponse(content=payload.model_dump(mode="json"))
    attach_auth_cookie(response, token)
    if user.active_workspace_id is not None:
        set_active_workspace_cookie(response, user.active_workspace_id)
    else:
        clear_active_workspace_cookie(response)
    return response


@router.post("", response_model=CurrentUserResponse)
async def start_supervision(
    data: SupervisionStartRequest,
    request: Request,
    owner: UserDB = Depends(require_instance_owner),
    service: SupervisionService = Depends(get_supervision_service),
) -> JSONResponse:
    if detect_auth_method(request, owner) != "cookie":
        raise PermissionDeniedError("Supervision requires a browser session")
    claims = getattr(request.state, "session_claims", None)
    if not isinstance(claims, SessionClaims) or claims.is_supervised:
        raise PermissionDeniedError("Supervision requires an owner session")

    target = await service.resolve_target(
        actor_id=owner.id,
        user_id=data.user_id,
        workspace_id=data.workspace_id,
    )
    token = create_access_token(
        target.id,
        auth_time=claims.auth_time,
        remember_me=claims.remember_me,
        actor_id=owner.id,
        actor_workspace_id=owner.active_workspace_id,
    )
    return _response(
        target,
        token,
        supervision=SupervisionInfo(
            actor_id=owner.id,
            actor_name=owner.name,
            actor_email=owner.email,
            workspace_id=data.workspace_id,
        ),
    )


@router.delete("", response_model=CurrentUserResponse)
async def stop_supervision(
    context: SupervisionContext | None = Depends(get_supervision_context),
    service: SupervisionService = Depends(get_supervision_service),
) -> JSONResponse:
    if context is None:
        raise DomainValidationError("No supervision session is active")
    owner = await service.restore_actor(
        context.actor.id,
        context.claims.actor_workspace_id,
    )
    token = create_access_token(
        owner.id,
        auth_time=context.claims.auth_time,
        remember_me=context.claims.remember_me,
    )
    return _response(owner, token, supervision=None)
