from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.realtime.models import WorkspaceEventOutboxDB
from app.repository import BaseRepository


class WorkspaceEventOutboxRepository(BaseRepository[WorkspaceEventOutboxDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkspaceEventOutboxDB, db)

    async def enqueue(
        self,
        *,
        workspace_id: UUID,
        kind: str,
        target_user_id: UUID | None = None,
        thread_id: str | None = None,
        payload: dict | None = None,
    ) -> None:
        self.db.add(
            WorkspaceEventOutboxDB(
                workspace_id=workspace_id,
                target_user_id=target_user_id,
                kind=kind,
                thread_id=thread_id,
                payload=payload,
            )
        )

    async def claim_batch(self, limit: int) -> list[WorkspaceEventOutboxDB]:
        stmt = (
            select(WorkspaceEventOutboxDB)
            .order_by(
                col(WorkspaceEventOutboxDB.created_at),
                col(WorkspaceEventOutboxDB.id),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_batch(self, ids: list[UUID]) -> None:
        if not ids:
            return
        stmt = delete(WorkspaceEventOutboxDB).where(
            col(WorkspaceEventOutboxDB.id).in_(ids)
        )
        await self.db.execute(stmt)
