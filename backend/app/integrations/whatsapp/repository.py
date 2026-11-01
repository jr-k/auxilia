from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.integrations.whatsapp.db_models import (
    AgentWhatsAppConnectionDB,
    WhatsAppApprovalActionDB,
    WhatsAppContextMessageDB,
    WhatsAppDeliveryCursorDB,
    WhatsAppIdentityDB,
    WhatsAppOutboundMessageDB,
    WhatsAppSessionDB,
    WhatsAppThreadBindingDB,
    WhatsAppUpdateStatus,
    WhatsAppWebhookEventDB,
    WhatsAppWorkspaceSettingsDB,
)
from app.repository import BaseRepository


class WhatsAppWorkspaceSettingsRepository(BaseRepository[WhatsAppWorkspaceSettingsDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppWorkspaceSettingsDB, db)

    async def get_for_workspace(
        self, workspace_id: UUID
    ) -> WhatsAppWorkspaceSettingsDB | None:
        stmt = select(WhatsAppWorkspaceSettingsDB).where(
            WhatsAppWorkspaceSettingsDB.workspace_id == workspace_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class AgentWhatsAppConnectionRepository(BaseRepository[AgentWhatsAppConnectionDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentWhatsAppConnectionDB, db)

    async def list_for_agent(
        self, workspace_id: UUID, agent_id: UUID
    ) -> list[AgentWhatsAppConnectionDB]:
        stmt = (
            select(AgentWhatsAppConnectionDB)
            .where(
                AgentWhatsAppConnectionDB.workspace_id == workspace_id,
                AgentWhatsAppConnectionDB.agent_id == agent_id,
            )
            .order_by(
                col(AgentWhatsAppConnectionDB.created_at),
                col(AgentWhatsAppConnectionDB.id),
            )
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_for_workspace(
        self, workspace_id: UUID
    ) -> list[AgentWhatsAppConnectionDB]:
        stmt = select(AgentWhatsAppConnectionDB).where(
            AgentWhatsAppConnectionDB.workspace_id == workspace_id
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_for_scope(
        self, workspace_id: UUID, agent_id: UUID, connection_id: UUID
    ) -> AgentWhatsAppConnectionDB | None:
        stmt = select(AgentWhatsAppConnectionDB).where(
            AgentWhatsAppConnectionDB.id == connection_id,
            AgentWhatsAppConnectionDB.workspace_id == workspace_id,
            AgentWhatsAppConnectionDB.agent_id == agent_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_phone_number_id(
        self, phone_number_id: str
    ) -> AgentWhatsAppConnectionDB | None:
        stmt = select(AgentWhatsAppConnectionDB).where(
            AgentWhatsAppConnectionDB.phone_number_id == phone_number_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class WhatsAppIdentityRepository(BaseRepository[WhatsAppIdentityDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppIdentityDB, db)

    async def get_external(
        self, workspace_id: UUID, whatsapp_user_id: str
    ) -> WhatsAppIdentityDB | None:
        stmt = select(WhatsAppIdentityDB).where(
            WhatsAppIdentityDB.workspace_id == workspace_id,
            WhatsAppIdentityDB.whatsapp_user_id == whatsapp_user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_for_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> WhatsAppIdentityDB | None:
        stmt = select(WhatsAppIdentityDB).where(
            WhatsAppIdentityDB.workspace_id == workspace_id,
            WhatsAppIdentityDB.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def unlink(self, workspace_id: UUID, user_id: UUID) -> None:
        stmt = delete(WhatsAppIdentityDB).where(
            col(WhatsAppIdentityDB.workspace_id) == workspace_id,
            col(WhatsAppIdentityDB.user_id) == user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()


class WhatsAppSessionRepository(BaseRepository[WhatsAppSessionDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppSessionDB, db)

    async def get_recipient(
        self, connection_id: UUID, recipient_type: str, recipient_id: str
    ) -> WhatsAppSessionDB | None:
        stmt = select(WhatsAppSessionDB).where(
            WhatsAppSessionDB.whatsapp_connection_id == connection_id,
            WhatsAppSessionDB.recipient_type == recipient_type,
            WhatsAppSessionDB.recipient_id == recipient_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def touch(
        self,
        connection_id: UUID,
        recipient_type: str,
        recipient_id: str,
        at: datetime,
    ) -> WhatsAppSessionDB:
        row = await self.get_recipient(connection_id, recipient_type, recipient_id)
        if row is None:
            row = WhatsAppSessionDB(
                whatsapp_connection_id=connection_id,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                last_user_message_at=at,
            )
        elif at > row.last_user_message_at:
            row.last_user_message_at = at
        self.db.add(row)
        await self.db.flush()
        return row


class WhatsAppThreadBindingRepository(BaseRepository[WhatsAppThreadBindingDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppThreadBindingDB, db)

    async def get_external(
        self, connection_id: UUID, chat_id: str, whatsapp_user_id: str
    ) -> WhatsAppThreadBindingDB | None:
        stmt = select(WhatsAppThreadBindingDB).where(
            WhatsAppThreadBindingDB.whatsapp_connection_id == connection_id,
            WhatsAppThreadBindingDB.chat_id == chat_id,
            WhatsAppThreadBindingDB.whatsapp_user_id == whatsapp_user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_for_thread(self, thread_id: str) -> WhatsAppThreadBindingDB | None:
        stmt = select(WhatsAppThreadBindingDB).where(
            WhatsAppThreadBindingDB.thread_id == thread_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_private_for_identity(
        self, connection_ids: list[UUID], whatsapp_user_id: str
    ) -> WhatsAppThreadBindingDB | None:
        if not connection_ids:
            return None
        stmt = (
            select(WhatsAppThreadBindingDB)
            .where(
                col(WhatsAppThreadBindingDB.whatsapp_connection_id).in_(connection_ids),
                WhatsAppThreadBindingDB.whatsapp_user_id == whatsapp_user_id,
                WhatsAppThreadBindingDB.chat_id == whatsapp_user_id,
            )
            .order_by(col(WhatsAppThreadBindingDB.updated_at).desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def delete_for_identity(
        self, connection_ids: list[UUID], whatsapp_user_id: str
    ) -> None:
        if not connection_ids:
            return
        stmt = delete(WhatsAppThreadBindingDB).where(
            col(WhatsAppThreadBindingDB.whatsapp_connection_id).in_(connection_ids),
            col(WhatsAppThreadBindingDB.whatsapp_user_id) == whatsapp_user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()


class WhatsAppApprovalRepository(BaseRepository[WhatsAppApprovalActionDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppApprovalActionDB, db)

    async def get_token(self, token: str) -> WhatsAppApprovalActionDB | None:
        stmt = select(WhatsAppApprovalActionDB).where(
            WhatsAppApprovalActionDB.token == token
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_interrupt(
        self, thread_id: str, interrupt_id: str, *, for_update: bool = False
    ) -> list[WhatsAppApprovalActionDB]:
        stmt = (
            select(WhatsAppApprovalActionDB)
            .where(
                WhatsAppApprovalActionDB.thread_id == thread_id,
                WhatsAppApprovalActionDB.interrupt_id == interrupt_id,
            )
            .order_by(
                col(WhatsAppApprovalActionDB.created_at),
                col(WhatsAppApprovalActionDB.id),
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        return list((await self.db.execute(stmt)).scalars().all())


class WhatsAppWebhookEventRepository(BaseRepository[WhatsAppWebhookEventDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppWebhookEventDB, db)

    async def get_external(
        self, connection_id: UUID, event_key: str
    ) -> WhatsAppWebhookEventDB | None:
        stmt = select(WhatsAppWebhookEventDB).where(
            WhatsAppWebhookEventDB.whatsapp_connection_id == connection_id,
            WhatsAppWebhookEventDB.event_key == event_key,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def claim_pending(self, limit: int = 20) -> list[WhatsAppWebhookEventDB]:
        stmt = (
            select(WhatsAppWebhookEventDB)
            .where(
                col(WhatsAppWebhookEventDB.status).in_(
                    [WhatsAppUpdateStatus.pending, WhatsAppUpdateStatus.failed]
                ),
                WhatsAppWebhookEventDB.attempts < 10,
            )
            .order_by(
                col(WhatsAppWebhookEventDB.created_at),
                col(WhatsAppWebhookEventDB.id),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        for row in rows:
            row.status = WhatsAppUpdateStatus.processing
            row.attempts += 1
            row.last_error = None
            self.db.add(row)
        await self.db.flush()
        return rows

    async def requeue_stale(self) -> None:
        stmt = (
            update(WhatsAppWebhookEventDB)
            .where(
                col(WhatsAppWebhookEventDB.status) == WhatsAppUpdateStatus.processing,
                col(WhatsAppWebhookEventDB.updated_at)
                < datetime.now(UTC) - timedelta(minutes=5),
            )
            .values(status=WhatsAppUpdateStatus.failed)
        )
        await self.db.execute(stmt)

    async def purge_completed(self) -> None:
        stmt = delete(WhatsAppWebhookEventDB).where(
            col(WhatsAppWebhookEventDB.status) == WhatsAppUpdateStatus.completed,
            col(WhatsAppWebhookEventDB.created_at)
            < datetime.now(UTC) - timedelta(days=30),
        )
        await self.db.execute(stmt)


class WhatsAppOutboundMessageRepository(BaseRepository[WhatsAppOutboundMessageDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppOutboundMessageDB, db)

    async def get_message(
        self, connection_id: UUID, message_id: str
    ) -> WhatsAppOutboundMessageDB | None:
        stmt = select(WhatsAppOutboundMessageDB).where(
            WhatsAppOutboundMessageDB.whatsapp_connection_id == connection_id,
            WhatsAppOutboundMessageDB.message_id == message_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class WhatsAppContextRepository(BaseRepository[WhatsAppContextMessageDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppContextMessageDB, db)

    async def list_since(
        self,
        connection_id: UUID,
        chat_id: str,
        after: datetime | None,
        *,
        limit: int = 50,
    ) -> list[WhatsAppContextMessageDB]:
        stmt = (
            select(WhatsAppContextMessageDB)
            .where(
                WhatsAppContextMessageDB.whatsapp_connection_id == connection_id,
                WhatsAppContextMessageDB.chat_id == chat_id,
                WhatsAppContextMessageDB.expires_at > datetime.now(UTC),
            )
            .order_by(
                col(WhatsAppContextMessageDB.sent_at),
                col(WhatsAppContextMessageDB.id),
            )
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(WhatsAppContextMessageDB.sent_at > after)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_message(
        self, connection_id: UUID, message_id: str
    ) -> WhatsAppContextMessageDB | None:
        stmt = select(WhatsAppContextMessageDB).where(
            WhatsAppContextMessageDB.whatsapp_connection_id == connection_id,
            WhatsAppContextMessageDB.message_id == message_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def purge_expired(self) -> None:
        stmt = delete(WhatsAppContextMessageDB).where(
            col(WhatsAppContextMessageDB.expires_at) <= datetime.now(UTC)
        )
        await self.db.execute(stmt)


class WhatsAppDeliveryCursorRepository(BaseRepository[WhatsAppDeliveryCursorDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppDeliveryCursorDB, db)

    async def get_for_run(self, run_id: str) -> WhatsAppDeliveryCursorDB | None:
        stmt = select(WhatsAppDeliveryCursorDB).where(
            WhatsAppDeliveryCursorDB.run_id == run_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
