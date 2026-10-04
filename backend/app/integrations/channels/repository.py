from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.notifications.models import (
    ExternalActionDB,
    ExternalConversationDB,
    ExternalIdentityDB,
    ExternalProvider,
)
from app.repository import BaseRepository


class ExternalIdentityRepository(BaseRepository[ExternalIdentityDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(ExternalIdentityDB, db)

    async def get_external(
        self,
        workspace_id: UUID,
        provider: ExternalProvider,
        external_user_id: str,
    ) -> ExternalIdentityDB | None:
        stmt = select(ExternalIdentityDB).where(
            ExternalIdentityDB.workspace_id == workspace_id,
            ExternalIdentityDB.provider == provider,
            ExternalIdentityDB.external_user_id == external_user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_user(
        self, workspace_id: UUID, provider: ExternalProvider, user_id: UUID
    ) -> ExternalIdentityDB | None:
        stmt = select(ExternalIdentityDB).where(
            ExternalIdentityDB.workspace_id == workspace_id,
            ExternalIdentityDB.provider == provider,
            ExternalIdentityDB.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> list[ExternalIdentityDB]:
        stmt = (
            select(ExternalIdentityDB)
            .where(
                ExternalIdentityDB.workspace_id == workspace_id,
                ExternalIdentityDB.user_id == user_id,
            )
            .order_by(ExternalIdentityDB.provider)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def unlink(
        self, workspace_id: UUID, provider: ExternalProvider, user_id: UUID
    ) -> None:
        stmt = delete(ExternalIdentityDB).where(
            col(ExternalIdentityDB.workspace_id) == workspace_id,
            col(ExternalIdentityDB.provider) == provider,
            col(ExternalIdentityDB.user_id) == user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()


class ExternalConversationRepository(BaseRepository[ExternalConversationDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(ExternalConversationDB, db)

    async def get_scope(
        self,
        workspace_id: UUID,
        provider: ExternalProvider,
        external_chat_id: str,
        external_thread_id: str,
        external_user_id: str,
    ) -> ExternalConversationDB | None:
        stmt = select(ExternalConversationDB).where(
            ExternalConversationDB.workspace_id == workspace_id,
            ExternalConversationDB.provider == provider,
            ExternalConversationDB.external_chat_id == external_chat_id,
            ExternalConversationDB.external_thread_id == external_thread_id,
            ExternalConversationDB.external_user_id == external_user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_for_identity(
        self,
        workspace_id: UUID,
        provider: ExternalProvider,
        external_user_id: str,
    ) -> None:
        stmt = delete(ExternalConversationDB).where(
            col(ExternalConversationDB.workspace_id) == workspace_id,
            col(ExternalConversationDB.provider) == provider,
            col(ExternalConversationDB.external_user_id) == external_user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()


class ExternalActionRepository(BaseRepository[ExternalActionDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(ExternalActionDB, db)

    async def get_token(
        self, provider: ExternalProvider, token: str
    ) -> ExternalActionDB | None:
        stmt = select(ExternalActionDB).where(
            ExternalActionDB.provider == provider,
            ExternalActionDB.token == token,
            ExternalActionDB.expires_at > datetime.now(UTC),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_interrupt(
        self,
        provider: ExternalProvider,
        thread_id: str,
        interrupt_id: str,
        *,
        for_update: bool = False,
    ) -> list[ExternalActionDB]:
        stmt = (
            select(ExternalActionDB)
            .where(
                ExternalActionDB.provider == provider,
                ExternalActionDB.thread_id == thread_id,
                ExternalActionDB.interrupt_id == interrupt_id,
                ExternalActionDB.expires_at > datetime.now(UTC),
            )
            .order_by(col(ExternalActionDB.created_at), col(ExternalActionDB.id))
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
