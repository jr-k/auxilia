import logging

from app.background import PeriodicLoop
from app.database import AsyncSessionLocal
from app.realtime.events import WorkspaceEventStream
from app.realtime.repository import WorkspaceEventOutboxRepository


logger = logging.getLogger(__name__)

_RELAY_INTERVAL_SECONDS = 0.25
_BATCH_SIZE = 100


class WorkspaceEventRelay:
    """Moves committed outbox rows to workspace Redis Streams."""

    def __init__(self, redis=None):
        self._redis = redis
        self._loop = PeriodicLoop(
            "workspace-event-relay",
            _RELAY_INTERVAL_SECONDS,
            self._relay_batch,
        )

    async def run(self) -> None:
        logger.info("workspace event relay started")
        await self._loop.run()

    async def _relay_batch(self) -> None:
        async with AsyncSessionLocal() as db:
            repository = WorkspaceEventOutboxRepository(db)
            rows = await repository.claim_batch(_BATCH_SIZE)
            if not rows:
                return
            for row in rows:
                await WorkspaceEventStream(
                    row.workspace_id,
                    self._redis,
                ).publish(row)
            await repository.delete_batch([row.id for row in rows])
            await db.commit()

    def stop(self) -> None:
        self._loop.stop()
