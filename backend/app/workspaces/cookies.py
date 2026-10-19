from uuid import UUID

from fastapi import Response

from app.auth.settings import auth_settings
from app.workspaces.constants import ACTIVE_WORKSPACE_COOKIE


def set_active_workspace_cookie(response: Response, workspace_id: UUID) -> None:
    response.set_cookie(
        key=ACTIVE_WORKSPACE_COOKIE,
        value=str(workspace_id),
        httponly=True,
        secure=auth_settings.COOKIE_SECURE,
        samesite=auth_settings.COOKIE_SAMESITE,
        domain=auth_settings.COOKIE_DOMAIN,
        max_age=auth_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def clear_active_workspace_cookie(response: Response) -> None:
    response.delete_cookie(
        key=ACTIVE_WORKSPACE_COOKIE,
        secure=auth_settings.COOKIE_SECURE,
        samesite=auth_settings.COOKIE_SAMESITE,
        domain=auth_settings.COOKIE_DOMAIN,
    )
