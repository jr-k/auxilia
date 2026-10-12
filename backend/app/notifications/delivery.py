import logging
from typing import cast
from uuid import UUID

from app.database import AsyncSessionLocal
from app.notifications.descriptor import (
    NOTIFICATION_CHANNEL,
    NotificationDelivery,
)
from app.notifications.service import NotificationChannelService
from app.runtime.agent import read_run_result
from app.runtime.runs.delivery import DeliveryConsumer
from app.runtime.runs.models import RunDB
from app.runtime.runs.service import RunService
from app.runtime.runs.state import RunStatus


logger = logging.getLogger(__name__)


def build_notification_run_consumer(
    record: RunDB,
) -> "NotificationRunConsumer | None":
    delivery = record.delivery
    if not delivery or delivery.get("channel") != NOTIFICATION_CHANNEL:
        return None
    if delivery.get("workspace_id") != str(record.workspace_id) or delivery.get(
        "user_id"
    ) != str(record.user_id):
        logger.error("Notification delivery scope mismatch for run %s", record.id)
        return None
    return NotificationRunConsumer(record)


class NotificationRunConsumer(DeliveryConsumer):
    def __init__(self, record: RunDB):
        self.record = record
        self.delivery = cast(NotificationDelivery, record.delivery or {})

    async def run(self) -> None:
        terminal = await RunService().wait_for_terminal(self.record.id)
        title = self.delivery["title"]
        if terminal.status is RunStatus.success:
            result = await read_run_result(
                self.record.workspace_id, self.record.thread_id
            )
            body = str(result.get("content") or "The scheduled task completed.")
        elif terminal.status is RunStatus.interrupted:
            body = "The scheduled task needs your approval before it can continue."
        elif terminal.status is RunStatus.cancelled:
            return
        else:
            detail = terminal.error or "The scheduled task could not be completed."
            body = f"Scheduled task failed: {detail}"

        raw_ids = self.delivery.get("channel_ids")
        channel_ids = (
            [UUID(channel_id) for channel_id in raw_ids]
            if raw_ids is not None
            else None
        )
        async with AsyncSessionLocal() as db:
            agent_id = await self._thread_agent_id(db)
            await NotificationChannelService(db, self.record.workspace_id).send(
                user_id=self.record.user_id,
                title=title,
                body=body,
                agent_id=agent_id,
                url=(
                    f"/agents/{agent_id}/chat/{self.record.thread_id}"
                    if agent_id is not None
                    else None
                ),
                channel_ids=channel_ids,
            )

    async def _thread_agent_id(self, db) -> UUID | None:
        from app.threads.repository import ThreadRepository

        thread = await ThreadRepository(db, self.record.workspace_id).get(
            self.record.thread_id
        )
        return thread.agent_id if thread is not None else None
