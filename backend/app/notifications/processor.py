import asyncio
import json
import logging
from uuid import UUID

import aiohttp
from pywebpush import WebPushException, webpush_async

from app.background import PeriodicLoop
from app.database import AsyncSessionLocal
from app.notifications.models import WebPushDeliveryStatus
from app.notifications.repository import (
    WebPushDeliveryRepository,
    WebPushSubscriptionRepository,
)
from app.notifications.settings import web_push_settings
from app.utils.encryption import decrypt_value


logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
EXPIRED_STATUS_CODES = {404, 410}


class WebPushDeliveryProcessor:
    def __init__(self) -> None:
        self._loop = PeriodicLoop(
            "web-push-delivery-processor",
            web_push_settings.delivery_interval_seconds,
            self._tick,
        )
        self._session: aiohttp.ClientSession | None = None

    async def run(self) -> None:
        async with aiohttp.ClientSession() as session:
            self._session = session
            try:
                await self._loop.run()
            finally:
                self._session = None

    def stop(self) -> None:
        self._loop.stop()

    async def _tick(self) -> None:
        async with AsyncSessionLocal() as db:
            deliveries = WebPushDeliveryRepository(db)
            await deliveries.requeue_stale()
            row_ids = await deliveries.claim_pending(limit=20)
            await db.commit()
        await asyncio.gather(*(self._process_safely(row_id) for row_id in row_ids))

    async def _process_safely(self, row_id: UUID) -> None:
        try:
            await self._process(row_id)
        except Exception as exc:
            # One corrupt subscription must not strand the rest of the claimed
            # batch. Retry it independently and keep the supervised tick healthy.
            logger.exception("Unexpected Web Push delivery failure: %s", row_id)
            await self._retry(row_id, type(exc).__name__)

    async def _process(self, row_id: UUID) -> None:
        async with AsyncSessionLocal() as db:
            deliveries = WebPushDeliveryRepository(db)
            row = await deliveries.get(row_id)
            if row is None or row.status is not WebPushDeliveryStatus.processing:
                return
            subscription = await WebPushSubscriptionRepository(db).get(
                row.subscription_id
            )
            if subscription is None:
                await deliveries.delete(row)
                await db.commit()
                return
            subscription_info = {
                "endpoint": decrypt_value(subscription.endpoint_encrypted),
                "keys": {
                    "p256dh": decrypt_value(subscription.p256dh_encrypted),
                    "auth": decrypt_value(subscription.auth_encrypted),
                },
            }
            payload = json.dumps(row.payload, separators=(",", ":"))

        session = self._session
        if session is None:
            await self._retry(row_id, "ProcessorStopped")
            return
        try:
            await webpush_async(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=web_push_settings.vapid_private_key,
                vapid_claims={"sub": web_push_settings.vapid_subject},
                ttl=web_push_settings.ttl_seconds,
                timeout=15,
                aiohttp_session=session,
            )
        except WebPushException as exc:
            status_code = exc.status_code
            if status_code in EXPIRED_STATUS_CODES:
                await self._delete_expired_subscription(row_id)
                return
            if status_code is None or status_code in TRANSIENT_STATUS_CODES:
                await self._retry(row_id, type(exc).__name__)
                return
            logger.warning(
                "Permanent Web Push failure for delivery %s: status=%s",
                row_id,
                status_code,
            )
            await self._discard(row_id)
            return
        except (aiohttp.ClientError, TimeoutError) as exc:
            await self._retry(row_id, type(exc).__name__)
            return
        await self._discard(row_id)

    async def _retry(self, row_id: UUID, error: str) -> None:
        async with AsyncSessionLocal() as db:
            deliveries = WebPushDeliveryRepository(db)
            row = await deliveries.get(row_id)
            if row is None:
                return
            next_attempt = row.attempts + 1
            if next_attempt >= web_push_settings.max_attempts:
                logger.warning(
                    "Web Push delivery %s exhausted %s attempts",
                    row_id,
                    next_attempt,
                )
                await deliveries.delete(row)
            else:
                await deliveries.reschedule(
                    row,
                    delay_seconds=min(2**next_attempt, 60),
                    error=error,
                )
            await db.commit()

    async def _discard(self, row_id: UUID) -> None:
        async with AsyncSessionLocal() as db:
            deliveries = WebPushDeliveryRepository(db)
            row = await deliveries.get(row_id)
            if row is not None:
                await deliveries.delete(row)
                await db.commit()

    async def _delete_expired_subscription(self, row_id: UUID) -> None:
        async with AsyncSessionLocal() as db:
            deliveries = WebPushDeliveryRepository(db)
            row = await deliveries.get(row_id)
            if row is None:
                return
            subscription = await WebPushSubscriptionRepository(db).get(
                row.subscription_id
            )
            if subscription is not None:
                await db.delete(subscription)
            else:
                await deliveries.delete(row)
            await db.commit()
