import hashlib
import hmac
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.integrations.whatsapp.db_models import WhatsAppWebhookEventDB
from app.integrations.whatsapp.repository import WhatsAppWebhookEventRepository
from app.integrations.whatsapp.service import WhatsAppConnectionService


router = APIRouter(prefix="/integrations/whatsapp", tags=["whatsapp"])


@router.get("/{connection_id}/webhook", response_class=PlainTextResponse)
async def verify_whatsapp_webhook(
    connection_id: UUID,
    mode: str | None = Query(default=None, alias="hub.mode"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    config = await WhatsAppConnectionService(db).get_runtime(connection_id)
    if config is None:
        raise HTTPException(status_code=404, detail="WhatsApp connection not found")
    if (
        mode != "subscribe"
        or challenge is None
        or verify_token is None
        or not hmac.compare_digest(verify_token, config.verify_token)
    ):
        raise HTTPException(status_code=403, detail="Invalid WhatsApp verify token")
    return PlainTextResponse(challenge)


@router.post("/{connection_id}/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def whatsapp_webhook(
    connection_id: UUID,
    request: Request,
    signature: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    db: AsyncSession = Depends(get_db),
) -> None:
    config = await WhatsAppConnectionService(db).get_runtime(connection_id)
    if config is None:
        raise HTTPException(status_code=404, detail="WhatsApp connection not found")
    raw = await request.body()
    if len(raw) > 5_000_000:
        raise HTTPException(status_code=413, detail="WhatsApp payload too large")
    expected = (
        "sha256="
        + hmac.new(config.app_secret.encode(), raw, hashlib.sha256).hexdigest()
    )
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp signature")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("object") != (
        "whatsapp_business_account"
    ):
        raise HTTPException(status_code=400, detail="Invalid WhatsApp event")
    phone_number_ids = _phone_number_ids(payload)
    if phone_number_ids and phone_number_ids != {config.phone_number_id}:
        raise HTTPException(status_code=400, detail="WhatsApp phone number mismatch")
    event_key = hashlib.sha256(raw).hexdigest()
    repository = WhatsAppWebhookEventRepository(db)
    if await repository.get_external(connection_id, event_key) is not None:
        return
    db.add(
        WhatsAppWebhookEventDB(
            whatsapp_connection_id=connection_id,
            event_key=event_key,
            payload=payload,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()


def _phone_number_ids(payload: dict) -> set[str]:
    result: set[str] = set()
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return result
    for entry in entries:
        changes = entry.get("changes") if isinstance(entry, dict) else None
        if not isinstance(changes, list):
            continue
        for change in changes:
            value = change.get("value") if isinstance(change, dict) else None
            metadata = value.get("metadata") if isinstance(value, dict) else None
            phone_number_id = (
                metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            )
            if isinstance(phone_number_id, str) and phone_number_id:
                result.add(phone_number_id)
    return result
