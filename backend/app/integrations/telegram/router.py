import asyncio
import hmac
import json
import logging
from collections.abc import Awaitable
from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request, status
from redis.exceptions import RedisError

from app.database import AsyncSessionLocal
from app.integrations.telegram.client import TelegramClient
from app.integrations.telegram.handlers import handle_update
from app.notifications.repository import TelegramNotificationSettingsRepository
from app.notifications.service import TelegramNotificationSettingsService
from app.redis_client import get_redis


router = APIRouter(prefix="/integrations/telegram", tags=["integrations"])
logger = logging.getLogger(__name__)

_COMPLETE_UPDATE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  redis.call('set', KEYS[1], 'completed', 'EX', ARGV[2])
  return 1
end
return 0
"""
_RELEASE_UPDATE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


async def _claim_update(key: str) -> str | None:
    redis = get_redis()
    owner = uuid4().hex
    for _ in range(20):
        if await redis.set(key, owner, ex=1800, nx=True):
            return owner
        state = await redis.get(key)
        if state == "completed":
            return None
        await asyncio.sleep(0.1)
    raise HTTPException(
        status_code=503, detail="Telegram update is still being processed"
    )


@router.post("/{bot_id}/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def telegram_webhook(
    bot_id: str,
    request: Request,
    secret_header: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> None:
    async with AsyncSessionLocal() as db:
        row = await TelegramNotificationSettingsRepository(db).get_by_bot_id(bot_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")
        config = await TelegramNotificationSettingsService(db).get_runtime_config(
            row.workspace_id
        )
    if (
        config is None
        or not secret_header
        or not hmac.compare_digest(secret_header, config.webhook_secret)
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")
    raw = await request.body()
    if len(raw) > 1_000_000:
        raise HTTPException(status_code=413, detail="Telegram payload too large")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    update_id = payload.get("update_id")
    dedupe_key: str | None = None
    dedupe_owner: str | None = None
    redis = get_redis()
    if update_id is not None:
        dedupe_key = f"telegram:update:{bot_id}:{update_id}"
        dedupe_owner = await _claim_update(dedupe_key)
        if dedupe_owner is None:
            return
    try:
        await handle_update(
            payload,
            workspace_id=config.workspace_id,
            client=TelegramClient(config.bot_token),
        )
    except Exception:
        if dedupe_key is not None and dedupe_owner is not None:
            try:
                await cast(
                    Awaitable[Any],
                    redis.eval(_RELEASE_UPDATE, 1, dedupe_key, dedupe_owner),
                )
            except RedisError:
                logger.warning(
                    "Could not release Telegram update lease %s",
                    dedupe_key,
                    exc_info=True,
                )
        raise
    if dedupe_key is not None and dedupe_owner is not None:
        try:
            completed = await cast(
                Awaitable[Any],
                redis.eval(
                    _COMPLETE_UPDATE,
                    1,
                    dedupe_key,
                    dedupe_owner,
                    "1800",
                ),
            )
        except RedisError:
            # The update itself succeeded. Returning 2xx avoids asking Telegram
            # to replay side effects; the owner lease remains as a second guard.
            logger.warning(
                "Could not mark Telegram update %s completed",
                dedupe_key,
                exc_info=True,
            )
        else:
            if not completed:
                raise HTTPException(
                    status_code=503,
                    detail="Telegram update lease ownership was lost",
                )
