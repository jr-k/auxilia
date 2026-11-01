import logging
import time
from uuid import UUID

from app.background import PeriodicLoop
from app.database import AsyncSessionLocal
from app.integrations.whatsapp.db_models import WhatsAppUpdateStatus
from app.integrations.whatsapp.handlers import handle_payload
from app.integrations.whatsapp.repository import (
    WhatsAppContextRepository,
    WhatsAppWebhookEventRepository,
)
from app.integrations.whatsapp.service import WhatsAppConnectionService


logger = logging.getLogger(__name__)


class WhatsAppUpdateProcessor:
    def __init__(self) -> None:
        self._last_purge_at = 0.0
        self._loop = PeriodicLoop("whatsapp-update-processor", 0.5, self._tick)

    async def run(self) -> None:
        await self._loop.run()

    def stop(self) -> None:
        self._loop.stop()

    async def _tick(self) -> None:
        async with AsyncSessionLocal() as db:
            events = WhatsAppWebhookEventRepository(db)
            await events.requeue_stale()
            rows = await events.claim_pending()
            now = time.monotonic()
            if now - self._last_purge_at >= 3600:
                await WhatsAppContextRepository(db).purge_expired()
                await events.purge_completed()
                self._last_purge_at = now
            await db.commit()
            row_ids = [row.id for row in rows]
        for row_id in row_ids:
            await self._process(row_id)

    async def _process(self, row_id: UUID) -> None:
        async with AsyncSessionLocal() as db:
            repository = WhatsAppWebhookEventRepository(db)
            row = await repository.get(row_id)
            if row is None or row.status is not WhatsAppUpdateStatus.processing:
                return
            config = await WhatsAppConnectionService(db).get_runtime(
                row.whatsapp_connection_id
            )
            if config is None or not config.enabled or not config.workspace_enabled:
                row.status = WhatsAppUpdateStatus.completed
                db.add(row)
                await db.commit()
                return
            try:
                await handle_payload(db, row.payload, config=config)
            except Exception as exc:
                await db.rollback()
                failed = await repository.get(row_id)
                if failed is not None:
                    failed.status = WhatsAppUpdateStatus.failed
                    failed.last_error = type(exc).__name__[:128]
                    db.add(failed)
                    await db.commit()
                logger.exception("WhatsApp event processing failed")
                return
            completed = await repository.get(row_id)
            if completed is not None:
                completed.status = WhatsAppUpdateStatus.completed
                completed.last_error = None
                db.add(completed)
                await db.commit()
