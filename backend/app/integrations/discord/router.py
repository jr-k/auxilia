import json
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.database import AsyncSessionLocal
from app.integrations.discord.handlers import (
    EPHEMERAL,
    handle_autocomplete,
    handle_link,
    handle_new,
    process_ask,
    process_hitl,
    subcommand,
)
from app.notifications.repository import DiscordNotificationSettingsRepository
from app.notifications.service import DiscordNotificationSettingsService
from app.redis_client import get_redis


router = APIRouter(prefix="/integrations/discord", tags=["integrations"])


@router.post("/interactions")
async def discord_interactions(
    request: Request,
    background: BackgroundTasks,
    signature: str | None = Header(default=None, alias="X-Signature-Ed25519"),
    timestamp: str | None = Header(default=None, alias="X-Signature-Timestamp"),
) -> dict:
    raw = await request.body()
    if len(raw) > 1_000_000:
        raise HTTPException(status_code=413, detail="Interaction payload too large")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    application_id = str(payload.get("application_id") or "")
    async with AsyncSessionLocal() as db:
        row = await DiscordNotificationSettingsRepository(db).get_by_application_id(
            application_id
        )
        config = (
            await DiscordNotificationSettingsService(db).get_runtime_config(
                row.workspace_id
            )
            if row
            else None
        )
    if config is None or not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Invalid Discord signature")
    try:
        if abs(time.time() - int(timestamp)) > 300:
            raise ValueError
        public_key = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(config.public_key)
        )
        public_key.verify(bytes.fromhex(signature), timestamp.encode() + raw)
    except (ValueError, OverflowError, InvalidSignature) as exc:
        raise HTTPException(
            status_code=401, detail="Invalid Discord signature"
        ) from exc

    interaction_type = payload.get("type")
    if interaction_type == 1:
        return {"type": 1}
    interaction_id = str(payload.get("id") or "")
    dedupe_key: str | None = None
    redis = get_redis()
    if interaction_id:
        dedupe_key = f"discord:interaction:{interaction_id}"
        first = await redis.set(dedupe_key, "processing", ex=30, nx=True)
        if not first:
            if await redis.get(dedupe_key) != "completed":
                raise HTTPException(
                    status_code=503,
                    detail="Discord interaction is still being processed",
                )
            return {
                "type": 4,
                "data": {"content": "Already handled.", "flags": EPHEMERAL},
            }
    try:
        if interaction_type == 4:
            response = await handle_autocomplete(payload, config.workspace_id)
        elif interaction_type == 3:
            background.add_task(
                process_hitl, payload, config.workspace_id, config.bot_token
            )
            response = {"type": 5, "data": {"flags": EPHEMERAL}}
        elif interaction_type == 2:
            command, _ = subcommand(payload)
            if command == "link":
                response = await handle_link(payload, config.workspace_id)
            elif command == "new":
                response = await handle_new(payload, config.workspace_id)
            elif command == "ask":
                background.add_task(
                    process_ask, payload, config.workspace_id, config.bot_token
                )
                response = {"type": 5}
            else:
                response = _unsupported()
        else:
            response = _unsupported()
    except Exception:
        if dedupe_key is not None:
            await redis.delete(dedupe_key)
        raise
    if dedupe_key is not None:
        await redis.set(dedupe_key, "completed", ex=600)
    return response


def _unsupported() -> dict:
    return {
        "type": 4,
        "data": {"content": "Unsupported command.", "flags": EPHEMERAL},
    }
