from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.integrations.telegram.db_models import (
    AgentTelegramBotDB,
    TelegramApprovalActionDB,
    TelegramContextMessageDB,
    TelegramDeliveryCursorDB,
    TelegramIdentityDB,
    TelegramThreadBindingDB,
    TelegramUpdateDB,
    TelegramUpdateStatus,
    TelegramWorkspaceSettingsDB,
)
from app.repository import BaseRepository


class TelegramWorkspaceSettingsRepository(BaseRepository[TelegramWorkspaceSettingsDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(TelegramWorkspaceSettingsDB, db)

    async def get_for_workspace(
        self, workspace_id: UUID
    ) -> TelegramWorkspaceSettingsDB | None:
        stmt = select(TelegramWorkspaceSettingsDB).where(
            TelegramWorkspaceSettingsDB.workspace_id == workspace_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class AgentTelegramBotRepository(BaseRepository[AgentTelegramBotDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentTelegramBotDB, db)

    async def list_for_agent(
        self, workspace_id: UUID, agent_id: UUID
    ) -> list[AgentTelegramBotDB]:
        stmt = (
            select(AgentTelegramBotDB)
            .where(
                AgentTelegramBotDB.workspace_id == workspace_id,
                AgentTelegramBotDB.agent_id == agent_id,
            )
            .order_by(col(AgentTelegramBotDB.created_at), col(AgentTelegramBotDB.id))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_for_workspace(self, workspace_id: UUID) -> list[AgentTelegramBotDB]:
        stmt = (
            select(AgentTelegramBotDB)
            .where(AgentTelegramBotDB.workspace_id == workspace_id)
            .order_by(
                col(AgentTelegramBotDB.agent_id).nulls_first(),
                col(AgentTelegramBotDB.created_at),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_for_scope(
        self, workspace_id: UUID, agent_id: UUID, bot_id: UUID
    ) -> AgentTelegramBotDB | None:
        stmt = select(AgentTelegramBotDB).where(
            AgentTelegramBotDB.id == bot_id,
            AgentTelegramBotDB.workspace_id == workspace_id,
            AgentTelegramBotDB.agent_id == agent_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_bot_id(
        self, external_bot_id: str
    ) -> AgentTelegramBotDB | None:
        stmt = select(AgentTelegramBotDB).where(
            AgentTelegramBotDB.bot_id == external_bot_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class TelegramIdentityRepository(BaseRepository[TelegramIdentityDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(TelegramIdentityDB, db)

    async def get_external(
        self, workspace_id: UUID, telegram_user_id: str
    ) -> TelegramIdentityDB | None:
        stmt = select(TelegramIdentityDB).where(
            TelegramIdentityDB.workspace_id == workspace_id,
            TelegramIdentityDB.telegram_user_id == telegram_user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> TelegramIdentityDB | None:
        stmt = select(TelegramIdentityDB).where(
            TelegramIdentityDB.workspace_id == workspace_id,
            TelegramIdentityDB.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def unlink(self, workspace_id: UUID, user_id: UUID) -> None:
        stmt = delete(TelegramIdentityDB).where(
            col(TelegramIdentityDB.workspace_id) == workspace_id,
            col(TelegramIdentityDB.user_id) == user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()


class TelegramThreadBindingRepository(BaseRepository[TelegramThreadBindingDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(TelegramThreadBindingDB, db)

    async def get_external(
        self,
        telegram_bot_id: UUID,
        chat_id: str,
        message_thread_id: str,
        telegram_user_id: str,
    ) -> TelegramThreadBindingDB | None:
        stmt = select(TelegramThreadBindingDB).where(
            TelegramThreadBindingDB.telegram_bot_id == telegram_bot_id,
            TelegramThreadBindingDB.chat_id == chat_id,
            TelegramThreadBindingDB.message_thread_id == message_thread_id,
            TelegramThreadBindingDB.telegram_user_id == telegram_user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_thread(self, thread_id: str) -> TelegramThreadBindingDB | None:
        stmt = select(TelegramThreadBindingDB).where(
            TelegramThreadBindingDB.thread_id == thread_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_for_identity(
        self, telegram_bot_ids: list[UUID], telegram_user_id: str
    ) -> None:
        if not telegram_bot_ids:
            return
        stmt = delete(TelegramThreadBindingDB).where(
            col(TelegramThreadBindingDB.telegram_bot_id).in_(telegram_bot_ids),
            col(TelegramThreadBindingDB.telegram_user_id) == telegram_user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()


class TelegramApprovalRepository(BaseRepository[TelegramApprovalActionDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(TelegramApprovalActionDB, db)

    async def get_token(self, token: str) -> TelegramApprovalActionDB | None:
        stmt = select(TelegramApprovalActionDB).where(
            TelegramApprovalActionDB.token == token
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_interrupt(
        self, thread_id: str, interrupt_id: str, *, for_update: bool = False
    ) -> list[TelegramApprovalActionDB]:
        stmt = (
            select(TelegramApprovalActionDB)
            .where(
                TelegramApprovalActionDB.thread_id == thread_id,
                TelegramApprovalActionDB.interrupt_id == interrupt_id,
            )
            .order_by(
                col(TelegramApprovalActionDB.created_at),
                col(TelegramApprovalActionDB.id),
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class TelegramUpdateRepository(BaseRepository[TelegramUpdateDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(TelegramUpdateDB, db)

    async def get_external(
        self, telegram_bot_id: UUID, update_id: int
    ) -> TelegramUpdateDB | None:
        stmt = select(TelegramUpdateDB).where(
            TelegramUpdateDB.telegram_bot_id == telegram_bot_id,
            TelegramUpdateDB.update_id == update_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_media_group(
        self, telegram_bot_id: UUID, media_group_id: str
    ) -> list[TelegramUpdateDB]:
        group_value = col(TelegramUpdateDB.payload)["message"][
            "media_group_id"
        ].as_string()
        stmt = (
            select(TelegramUpdateDB)
            .where(
                TelegramUpdateDB.telegram_bot_id == telegram_bot_id,
                group_value == media_group_id,
            )
            .order_by(col(TelegramUpdateDB.update_id))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def claim_pending(self, limit: int = 20) -> list[TelegramUpdateDB]:
        stmt = (
            select(TelegramUpdateDB)
            .where(
                col(TelegramUpdateDB.status).in_(
                    [TelegramUpdateStatus.pending, TelegramUpdateStatus.failed]
                ),
                TelegramUpdateDB.attempts < 10,
            )
            .order_by(col(TelegramUpdateDB.created_at), col(TelegramUpdateDB.id))
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        for row in rows:
            row.status = TelegramUpdateStatus.processing
            row.attempts += 1
            row.last_error = None
            self.db.add(row)
        await self.db.flush()
        return rows

    async def requeue_stale(self) -> None:
        stmt = (
            update(TelegramUpdateDB)
            .where(
                col(TelegramUpdateDB.status) == TelegramUpdateStatus.processing,
                col(TelegramUpdateDB.updated_at)
                < datetime.now(UTC) - timedelta(minutes=5),
            )
            .values(status=TelegramUpdateStatus.failed)
        )
        await self.db.execute(stmt)

    async def purge_completed(self) -> None:
        stmt = delete(TelegramUpdateDB).where(
            col(TelegramUpdateDB.status) == TelegramUpdateStatus.completed,
            col(TelegramUpdateDB.created_at) < datetime.now(UTC) - timedelta(days=30),
        )
        await self.db.execute(stmt)


class TelegramContextRepository(BaseRepository[TelegramContextMessageDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(TelegramContextMessageDB, db)

    async def list_since(
        self,
        telegram_bot_id: UUID,
        chat_id: str,
        message_thread_id: str,
        after_message_id: int | None,
        *,
        limit: int = 50,
    ) -> list[TelegramContextMessageDB]:
        stmt = (
            select(TelegramContextMessageDB)
            .where(
                TelegramContextMessageDB.telegram_bot_id == telegram_bot_id,
                TelegramContextMessageDB.chat_id == chat_id,
                TelegramContextMessageDB.message_thread_id == message_thread_id,
                TelegramContextMessageDB.expires_at > datetime.now(UTC),
            )
            .order_by(
                col(TelegramContextMessageDB.message_id),
                col(TelegramContextMessageDB.id),
            )
            .limit(limit)
        )
        if after_message_id is not None:
            stmt = stmt.where(TelegramContextMessageDB.message_id > after_message_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_message(
        self, telegram_bot_id: UUID, chat_id: str, message_id: int
    ) -> TelegramContextMessageDB | None:
        stmt = select(TelegramContextMessageDB).where(
            TelegramContextMessageDB.telegram_bot_id == telegram_bot_id,
            TelegramContextMessageDB.chat_id == chat_id,
            TelegramContextMessageDB.message_id == message_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def purge_expired(self) -> None:
        stmt = delete(TelegramContextMessageDB).where(
            col(TelegramContextMessageDB.expires_at) <= datetime.now(UTC)
        )
        await self.db.execute(stmt)


class TelegramDeliveryCursorRepository(BaseRepository[TelegramDeliveryCursorDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(TelegramDeliveryCursorDB, db)

    async def get_for_run(self, run_id: str) -> TelegramDeliveryCursorDB | None:
        stmt = select(TelegramDeliveryCursorDB).where(
            TelegramDeliveryCursorDB.run_id == run_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
