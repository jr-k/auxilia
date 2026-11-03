from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.notifications.models import (
    SlackNotificationSettingsDB,
    WebPushDeliveryDB,
    WebPushDeliveryStatus,
    WebPushSubscriptionDB,
)
from app.repository import BaseRepository


class SlackNotificationSettingsRepository(BaseRepository[SlackNotificationSettingsDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(SlackNotificationSettingsDB, db)

    async def get_settings(
        self, workspace_id: UUID | None = None
    ) -> SlackNotificationSettingsDB | None:
        stmt = select(SlackNotificationSettingsDB).where(
            SlackNotificationSettingsDB.key == "default"
        )
        if workspace_id is not None:
            stmt = stmt.where(SlackNotificationSettingsDB.workspace_id == workspace_id)
        else:
            stmt = stmt.limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_or_create(self, workspace_id: UUID) -> SlackNotificationSettingsDB:
        row = await self.get_settings(workspace_id)
        if row is not None:
            return row
        try:
            async with self.db.begin_nested():
                row = SlackNotificationSettingsDB(workspace_id=workspace_id)
                self.db.add(row)
                await self.db.flush()
        except IntegrityError:
            row = await self.get_settings(workspace_id)
            if row is None:
                raise
        return row

    async def save(
        self,
        *,
        workspace_id: UUID,
        enabled: bool,
    ) -> SlackNotificationSettingsDB:
        row = await self._get_or_create(workspace_id)
        row.enabled = enabled
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row


class WebPushSubscriptionRepository(BaseRepository[WebPushSubscriptionDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WebPushSubscriptionDB, db)

    async def get_by_endpoint_hash(
        self, endpoint_hash: str
    ) -> WebPushSubscriptionDB | None:
        stmt = select(WebPushSubscriptionDB).where(
            WebPushSubscriptionDB.endpoint_hash == endpoint_hash
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UUID) -> list[WebPushSubscriptionDB]:
        # Keep unsubscribe/ownership transfer from deleting a referenced row
        # between delivery staging and the run-finalization commit.
        stmt = (
            select(WebPushSubscriptionDB)
            .where(WebPushSubscriptionDB.user_id == user_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        user_id: UUID,
        endpoint_hash: str,
        endpoint_encrypted: str,
        p256dh_encrypted: str,
        auth_encrypted: str,
        user_agent: str | None,
    ) -> WebPushSubscriptionDB:
        row = await self.get_by_endpoint_hash(endpoint_hash)
        if row is None:
            try:
                async with self.db.begin_nested():
                    row = WebPushSubscriptionDB(
                        user_id=user_id,
                        endpoint_hash=endpoint_hash,
                        endpoint_encrypted=endpoint_encrypted,
                        p256dh_encrypted=p256dh_encrypted,
                        auth_encrypted=auth_encrypted,
                        user_agent=user_agent,
                    )
                    self.db.add(row)
                    await self.db.flush()
            except IntegrityError:
                row = await self.get_by_endpoint_hash(endpoint_hash)
                if row is None:
                    raise
        if row.user_id != user_id:
            stmt = delete(WebPushDeliveryDB).where(
                col(WebPushDeliveryDB.subscription_id) == row.id
            )
            await self.db.execute(stmt)
        row.user_id = user_id
        row.endpoint_encrypted = endpoint_encrypted
        row.p256dh_encrypted = p256dh_encrypted
        row.auth_encrypted = auth_encrypted
        row.user_agent = user_agent
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_for_user(self, user_id: UUID, endpoint_hash: str) -> bool:
        stmt = (
            delete(WebPushSubscriptionDB)
            .where(
                col(WebPushSubscriptionDB.user_id) == user_id,
                col(WebPushSubscriptionDB.endpoint_hash) == endpoint_hash,
            )
            .returning(col(WebPushSubscriptionDB.id))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None


class WebPushDeliveryRepository(BaseRepository[WebPushDeliveryDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WebPushDeliveryDB, db)

    async def enqueue_for_user(
        self,
        *,
        user_id: UUID,
        run_id: str,
        payload: dict,
    ) -> None:
        subscriptions = await WebPushSubscriptionRepository(self.db).list_for_user(
            user_id
        )
        now = datetime.now(UTC)
        self.db.add_all(
            [
                WebPushDeliveryDB(
                    subscription_id=subscription.id,
                    run_id=run_id,
                    next_attempt_at=now,
                    payload=payload,
                )
                for subscription in subscriptions
            ]
        )

    async def requeue_stale(self, stale_after_seconds: int = 300) -> None:
        stale_before = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        stmt = (
            update(WebPushDeliveryDB)
            .where(
                col(WebPushDeliveryDB.status) == WebPushDeliveryStatus.processing,
                col(WebPushDeliveryDB.claimed_at) < stale_before,
            )
            .values(
                status=WebPushDeliveryStatus.pending,
                claimed_at=None,
            )
        )
        await self.db.execute(stmt)

    async def claim_pending(self, limit: int = 50) -> list[UUID]:
        now = datetime.now(UTC)
        stmt = (
            select(WebPushDeliveryDB)
            .where(
                WebPushDeliveryDB.status == WebPushDeliveryStatus.pending,
                WebPushDeliveryDB.next_attempt_at <= now,
            )
            .order_by(
                col(WebPushDeliveryDB.next_attempt_at),
                col(WebPushDeliveryDB.created_at),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        for row in rows:
            row.status = WebPushDeliveryStatus.processing
            row.claimed_at = now
            self.db.add(row)
        await self.db.flush()
        return [row.id for row in rows]

    async def reschedule(
        self,
        row: WebPushDeliveryDB,
        *,
        delay_seconds: int,
        error: str,
    ) -> None:
        row.status = WebPushDeliveryStatus.pending
        row.attempts += 1
        row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        row.claimed_at = None
        row.last_error = error[:128]
        self.db.add(row)
        await self.db.flush()
