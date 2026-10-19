from contextlib import suppress
from uuid import UUID

from fastapi import Response
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth.settings import TWO_FACTOR_CHALLENGE_COOKIE, auth_settings
from app.auth.utils import attach_auth_cookie, renew_access_token
from app.workspaces.constants import ACTIVE_WORKSPACE_COOKIE
from app.workspaces.cookies import set_active_workspace_cookie


class SlidingSessionMiddleware:
    """Renew active browser sessions without depending on response shape."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cookies = HTTPConnection(scope).cookies
        token = cookies.get(auth_settings.COOKIE_NAME)
        renewed = renew_access_token(token) if token else None
        if renewed is None:
            await self.app(scope, receive, send)
            return

        carrier = Response()
        attach_auth_cookie(carrier, renewed)
        workspace_value = cookies.get(ACTIVE_WORKSPACE_COOKIE)
        if workspace_value is not None:
            with suppress(ValueError):
                set_active_workspace_cookie(carrier, UUID(workspace_value))
        renewal_cookies = carrier.headers.getlist("set-cookie")

        async def send_renewed(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] < 400:
                headers = MutableHeaders(scope=message)
                existing = headers.getlist("set-cookie")
                # A 2FA challenge must never inherit or renew an older full
                # session present in the browser.
                challenge = f"{TWO_FACTOR_CHALLENGE_COOKIE}="
                if not any(value.startswith(challenge) for value in existing):
                    for cookie in renewal_cookies:
                        name = cookie.partition("=")[0]
                        # Sign-in, sign-out, or a workspace switch wins over
                        # values read at the beginning of this request.
                        if not any(
                            value.startswith(f"{name}=") for value in existing
                        ):
                            headers.append("set-cookie", cookie)
            await send(message)

        await self.app(scope, receive, send_renewed)
