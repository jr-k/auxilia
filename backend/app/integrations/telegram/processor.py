import logging
import time
from uuid import UUID

from app.background import PeriodicLoop
from app.database import AsyncSessionLocal
from app.integrations.telegram.client import TelegramClient
from app.integrations.telegram.db_models import TelegramUpdateStatus
from app.integrations.telegram.handlers import handle_update
from app.integrations.telegram.repository import (
    TelegramContextRepository,
    TelegramUpdateRepository,
)
from app.integrations.telegram.service import TelegramBotService


logger = logging.getLogger(__name__)


class TelegramUpdateProcessor:
    """Claims durable webhook inbox rows and processes them outside the request."""

    def __init__(self) -> None:
        self._last_purge_at = 0.0
        self._loop = PeriodicLoop("telegram-update-processor", 0.5, self._tick)

    async def run(self) -> None:
        await self._loop.run()

    def stop(self) -> None:
        self._loop.stop()

    async def _tick(self) -> None:
        async with AsyncSessionLocal() as db:
            updates = TelegramUpdateRepository(db)
            await updates.requeue_stale()
            rows = await updates.claim_pending()
            now = time.monotonic()
            if now - self._last_purge_at >= 3600:
                await TelegramContextRepository(db).purge_expired()
                await updates.purge_completed()
                self._last_purge_at = now
            await db.commit()
            row_ids = [row.id for row in rows]
        for row_id in row_ids:
            await self._process(row_id)

    async def _process(self, row_id: UUID) -> None:
        async with AsyncSessionLocal() as db:
            row = await TelegramUpdateRepository(db).get(row_id)
            if row is None or row.status is not TelegramUpdateStatus.processing:
                return
            config = await TelegramBotService(db).get_runtime(row.telegram_bot_id)
            if config is None or not config.enabled or not config.workspace_enabled:
                row.status = TelegramUpdateStatus.completed
                db.add(row)
                await db.commit()
                return
            try:
                await handle_update(
                    db,
                    row.payload,
                    config=config,
                    client=TelegramClient(config.bot_token),
                )
            except Exception as exc:
                await db.rollback()
                failed = await TelegramUpdateRepository(db).get(row_id)
                if failed is not None:
                    failed.status = TelegramUpdateStatus.failed
                    failed.last_error = type(exc).__name__[:128]
                    db.add(failed)
                    await db.commit()
                logger.exception("Telegram update processing failed")
                return
            completed = await TelegramUpdateRepository(db).get(row_id)
            if completed is not None:
                completed.status = TelegramUpdateStatus.completed
                completed.last_error = None
                db.add(completed)
                await db.commit()
