from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.appearance.models import WorkspaceAppearanceDB
from app.repository import BaseRepository


class WorkspaceAppearanceRepository(BaseRepository[WorkspaceAppearanceDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkspaceAppearanceDB, db)

    async def get_settings(self) -> WorkspaceAppearanceDB | None:
        stmt = select(WorkspaceAppearanceDB).where(
            WorkspaceAppearanceDB.key == "default"
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self) -> WorkspaceAppearanceDB:
        row = await self.get_settings()
        if row is None:
            row = WorkspaceAppearanceDB()
            self.db.add(row)
            await self.db.flush()
            await self.db.refresh(row)
        return row
