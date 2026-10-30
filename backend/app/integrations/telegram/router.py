import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.integrations.telegram.db_models import TelegramUpdateDB
from app.integrations.telegram.repository import TelegramUpdateRepository
from app.integrations.telegram.service import TelegramBotService


router = APIRouter(prefix="/integrations/telegram", tags=["telegram"])


@router.post(
    "/{external_bot_id}/webhook",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def telegram_webhook(
    external_bot_id: str,
    request: Request,
    secret_header: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    config = await TelegramBotService(db).get_runtime_by_external_bot(external_bot_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Telegram bot not found")
    if not secret_header or not hmac.compare_digest(
        secret_header, config.webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")
    raw = await request.body()
    if len(raw) > 1_000_000:
        raise HTTPException(status_code=413, detail="Telegram payload too large")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("update_id"), int):
        raise HTTPException(status_code=400, detail="Invalid Telegram update")
    repository = TelegramUpdateRepository(db)
    if await repository.get_external(config.id, payload["update_id"]) is not None:
        return
    db.add(
        TelegramUpdateDB(
            telegram_bot_id=config.id,
            update_id=payload["update_id"],
            payload=payload,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
