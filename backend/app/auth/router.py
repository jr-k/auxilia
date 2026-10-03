from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.auth.configuration import (
    WorkspaceAuthenticationService,
    get_workspace_authentication_service,
)
from app.auth.dependencies import get_current_user, require_admin
from app.auth.schemas import (
    AuthMessageResponse,
    AuthProvidersResponse,
    InviteAcceptRequest,
    InviteInfoResponse,
    SetupStatusResponse,
    SigninRequest,
    SignupRequest,
    TwoFactorSigninResponse,
    TwoFactorSigninVerifyRequest,
    WorkspaceAuthenticationResponse,
    WorkspaceAuthenticationUpdate,
)
from app.auth.service import AuthService, get_auth_service
from app.auth.settings import auth_settings
from app.auth.two_factor import create_scoped_token
from app.exceptions import NoInviteError
from app.invites.service import InviteService, get_invite_service
from app.users.models import UserDB
from app.users.schemas import UserResponse


router = APIRouter(prefix="/auth", tags=["auth"])


def _attach_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth_settings.COOKIE_NAME,
        value=token,
        httponly=auth_settings.COOKIE_HTTPONLY,
        secure=auth_settings.COOKIE_SECURE,
        samesite=auth_settings.COOKIE_SAMESITE,
        domain=auth_settings.COOKIE_DOMAIN,
        max_age=auth_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _auth_response(user: UserDB, token: str, status_code: int = 200) -> JSONResponse:
    user_read = UserResponse.model_validate(user)
    response = JSONResponse(
        status_code=status_code,
        content=user_read.model_dump(mode="json"),
    )
    _attach_auth_cookie(response, token)
    return response


@router.get("/providers", response_model=AuthProvidersResponse)
async def get_auth_providers(
    service: AuthService = Depends(get_auth_service),
    authentication: WorkspaceAuthenticationService = Depends(
        get_workspace_authentication_service
    ),
) -> AuthProvidersResponse:
    user_count = await service.count_users()
    config = await authentication.get_runtime_config()
    return AuthProvidersResponse(
        password=await authentication.password_enabled(),
        google=config is not None,
        setup_required=user_count == 0,
    )


@router.get("/manage", response_model=WorkspaceAuthenticationResponse)
async def get_workspace_authentication(
    _: UserDB = Depends(require_admin),
    service: WorkspaceAuthenticationService = Depends(
        get_workspace_authentication_service
    ),
) -> WorkspaceAuthenticationResponse:
    return await service.get_response()


@router.put("/manage", response_model=WorkspaceAuthenticationResponse)
async def update_workspace_authentication(
    data: WorkspaceAuthenticationUpdate,
    _: UserDB = Depends(require_admin),
    service: WorkspaceAuthenticationService = Depends(
        get_workspace_authentication_service
    ),
) -> WorkspaceAuthenticationResponse:
    return await service.update(data)


@router.delete("/manage", response_model=WorkspaceAuthenticationResponse)
async def delete_workspace_authentication(
    _: UserDB = Depends(require_admin),
    service: WorkspaceAuthenticationService = Depends(
        get_workspace_authentication_service
    ),
) -> WorkspaceAuthenticationResponse:
    return await service.clear()


@router.get("/setup/status", response_model=SetupStatusResponse)
async def get_setup_status(
    service: AuthService = Depends(get_auth_service),
) -> SetupStatusResponse:
    return SetupStatusResponse(setup_required=await service.count_users() == 0)


@router.post("/setup", response_model=UserResponse, status_code=201)
async def setup(
    signup_data: SignupRequest,
    service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    user, token = await service.setup(signup_data)
    return _auth_response(user, token, status_code=201)


@router.post("/signin", response_model=UserResponse | TwoFactorSigninResponse)
async def signin(
    signin_data: SigninRequest,
    service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    user, token = await service.signin(signin_data)
    if user.two_factor_enabled:
        return JSONResponse(
            content=TwoFactorSigninResponse(challenge_token=token).model_dump(
                mode="json"
            )
        )
    return _auth_response(user, token)


@router.post("/signin/two-factor", response_model=UserResponse)
async def verify_two_factor_signin(
    data: TwoFactorSigninVerifyRequest,
    service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    user, token = await service.verify_two_factor_signin(data)
    return _auth_response(user, token)


@router.post("/signout", response_model=AuthMessageResponse)
async def signout() -> JSONResponse:
    response = JSONResponse(
        status_code=200,
        content={"message": "Successfully signed out"},
    )
    response.delete_cookie(
        key=auth_settings.COOKIE_NAME,
        httponly=auth_settings.COOKIE_HTTPONLY,
        secure=auth_settings.COOKIE_SECURE,
        samesite=auth_settings.COOKIE_SAMESITE,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    return response


@router.get("/invite/{token}", response_model=InviteInfoResponse)
async def get_invite_info(
    token: str,
    service: InviteService = Depends(get_invite_service),
    authentication: WorkspaceAuthenticationService = Depends(
        get_workspace_authentication_service
    ),
) -> InviteInfoResponse:
    invite = await service.get_by_token(token)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite",
        )
    return InviteInfoResponse(
        email=invite.email,
        role=invite.role,
        password_enabled=await authentication.password_enabled(),
        google_enabled=await authentication.get_runtime_config() is not None,
    )


@router.post("/invite/accept", response_model=UserResponse, status_code=201)
async def accept_invite(
    data: InviteAcceptRequest,
    service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    user, token = await service.accept_invite(data)
    return _auth_response(user, token, status_code=201)


@router.get("/google")
async def google_login(
    request: Request,
    invite_token: str | None = None,
    authentication: WorkspaceAuthenticationService = Depends(
        get_workspace_authentication_service
    ),
):
    oauth = await authentication.build_oauth()
    if oauth is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Google OAuth is not configured",
        )
    if invite_token:
        request.session["invite_token"] = invite_token

    client = oauth.create_client("google")
    return await client.authorize_redirect(request, authentication.callback_url)


@router.get("/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    service: AuthService = Depends(get_auth_service),
    authentication: WorkspaceAuthenticationService = Depends(
        get_workspace_authentication_service
    ),
):
    oauth = await authentication.build_oauth()
    if oauth is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Google OAuth is not configured",
        )

    try:
        client = oauth.create_client("google")
        token_data = await client.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {e!s}",
        ) from e

    userinfo = token_data.get("userinfo")
    if not userinfo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info from Google",
        )

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")
    if not google_sub or not email or userinfo.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return a verified email address",
        )

    invite_token = request.session.pop("invite_token", None)

    try:
        user, access_token = await service.oauth_signin_or_link(
            provider="google",
            sub_id=google_sub,
            email=email,
            name=userinfo.get("name"),
            picture_url=userinfo.get("picture"),
            invite_token=invite_token,
        )
    except NoInviteError:
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_URL}/auth?error=no_invite",
            status_code=302,
        )

    if user.two_factor_enabled:
        challenge = create_scoped_token(user.id, "two_factor_signin")
        return RedirectResponse(
            url=(
                f"{auth_settings.FRONTEND_URL}/auth"
                f"?two_factor_challenge={quote(challenge)}"
            ),
            status_code=302,
        )

    response = RedirectResponse(
        url=f"{auth_settings.FRONTEND_URL}/agents",
        status_code=302,
    )
    _attach_auth_cookie(response, access_token)
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: UserDB = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)
