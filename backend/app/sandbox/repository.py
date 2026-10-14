from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.repository import BaseRepository
from app.sandbox.models import SandboxDB, SandboxImageDB


class SandboxRepository(BaseRepository[SandboxDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(SandboxDB, db)

    async def list(self, workspace_id: UUID) -> list[SandboxDB]:
        stmt = (
            select(SandboxDB)
            .where(SandboxDB.workspace_id == workspace_id)
            .order_by(SandboxDB.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_scoped(
        self, sandbox_id: UUID, workspace_id: UUID
    ) -> SandboxDB | None:
        stmt = select(SandboxDB).where(
            SandboxDB.id == sandbox_id,
            SandboxDB.workspace_id == workspace_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_image(self, sandbox_id: UUID) -> SandboxImageDB | None:
        stmt = select(SandboxImageDB).where(SandboxImageDB.sandbox_id == sandbox_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _lock_image_parent(self, sandbox_id: UUID) -> None:
        stmt = select(SandboxDB.id).where(SandboxDB.id == sandbox_id).with_for_update()
        await self.db.execute(stmt)

    async def set_image(
        self,
        sandbox_id: UUID,
        *,
        data: bytes,
        media_type: str,
        sha256: str,
        revision: UUID,
    ) -> None:
        await self._lock_image_parent(sandbox_id)
        image = await self.get_image(sandbox_id)
        if image is None:
            image = SandboxImageDB(
                sandbox_id=sandbox_id,
                data=data,
                media_type=media_type,
                sha256=sha256,
            )
        else:
            image.data = data
            image.media_type = media_type
            image.sha256 = sha256
        self.db.add(image)
        stmt = (
            update(SandboxDB)
            .where(SandboxDB.id == sandbox_id)
            .values(image_revision=revision)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def delete_image(self, sandbox_id: UUID) -> None:
        await self._lock_image_parent(sandbox_id)
        stmt = delete(SandboxImageDB).where(SandboxImageDB.sandbox_id == sandbox_id)
        await self.db.execute(stmt)
        stmt = (
            update(SandboxDB)
            .where(SandboxDB.id == sandbox_id)
            .values(image_revision=None)
        )
        await self.db.execute(stmt)
        await self.db.flush()
