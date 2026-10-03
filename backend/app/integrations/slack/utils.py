import hashlib
import hmac
import logging
import time

import httpx
from fastapi import Header, HTTPException, Request
from slack_sdk.web.async_client import AsyncWebClient

from app.database import AsyncSessionLocal
from app.integrations.slack.models import SlackUserInfo
from app.notifications.service import SlackNotificationSettingsService
from app.users.models import UserDB
from app.users.repository import UserRepository


logger = logging.getLogger(__name__)

_MAX_AGE_SECONDS = 60 * 5


async def verify_slack_signature(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...),
) -> bytes:
    """FastAPI dependency that verifies the Slack request signature.

    Returns the raw request body so downstream handlers don't need to
    read it a second time.
    """
    timestamp = int(x_slack_request_timestamp)
    age = abs(time.time() - timestamp)
    if age > _MAX_AGE_SECONDS:
        raise HTTPException(status_code=403, detail="Request too old")

    body = await request.body()
    async with AsyncSessionLocal() as db:
        config = await SlackNotificationSettingsService(db).get_runtime_config()
    if config is None:
        raise HTTPException(status_code=503, detail="Slack is not configured")

    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected = (
        "v0="
        + hmac.new(
            config.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    match = hmac.compare_digest(expected, x_slack_signature)

    if not match:
        raise HTTPException(status_code=403, detail="Invalid signature")

    return body


async def get_slack_client() -> AsyncWebClient | None:
    async with AsyncSessionLocal() as db:
        config = await SlackNotificationSettingsService(db).get_runtime_config()
    return AsyncWebClient(token=config.bot_token) if config else None


async def get_user_info(user_id: str) -> SlackUserInfo | None:
    """Get user information from Slack API."""
    url = "https://slack.com/api/users.info"
    slack_client = await get_slack_client()
    if slack_client is None:
        return None
    headers = {"Authorization": f"Bearer {slack_client.token}"}
    params = {"user": user_id}

    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            if data.get("ok"):
                return SlackUserInfo.model_validate(data.get("user"))
            logger.warning("Slack API error (users.info): %s", data.get("error"))
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                "HTTP error calling Slack API (users.info): %s - %s",
                e.response.status_code,
                e.response.text,
            )
            return None
        except Exception:
            logger.exception("Unexpected error calling Slack API (users.info)")
            return None


async def resolve_user(slack_user_id: str) -> UserDB | None:
    """Map a Slack user ID to an internal user via email lookup."""
    user_info = await get_user_info(slack_user_id)
    if not user_info or not user_info.profile.email:
        return None
    async with AsyncSessionLocal() as db:
        return await UserRepository(db).get_by_email(user_info.profile.email)
