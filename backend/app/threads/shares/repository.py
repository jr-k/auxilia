from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.artifacts.models import ArtifactDB
from app.repository import BaseRepository
from app.threads.shares.models import (
    ConversationShareArtifactDB,
    ConversationShareDB,
)


class ConversationShareRepository(BaseRepository[ConversationShareDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(ConversationShareDB, db)

    async def get_for_thread(
        self, workspace_id: UUID, thread_id: str
    ) -> ConversationShareDB | None:
        stmt = select(ConversationShareDB).where(
            ConversationShareDB.workspace_id == workspace_id,
            ConversationShareDB.thread_id == thread_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def public_details(self, share_id: UUID) -> ConversationShareDB | None:
        stmt = select(ConversationShareDB).where(ConversationShareDB.id == share_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_artifacts(self, artifacts: list[ConversationShareArtifactDB]) -> None:
        self.db.add_all(artifacts)
        await self.db.flush()

    async def list_artifacts(self, share_id: UUID) -> list[ConversationShareArtifactDB]:
        stmt = (
            select(ConversationShareArtifactDB)
            .where(ConversationShareArtifactDB.share_id == share_id)
            .order_by(
                col(ConversationShareArtifactDB.created_at),
                col(ConversationShareArtifactDB.artifact_id),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def artifact(
        self, share_id: UUID, artifact_id: UUID
    ) -> tuple[ConversationShareArtifactDB, ArtifactDB] | None:
        stmt = (
            select(ConversationShareArtifactDB, ArtifactDB)
            .join(
                ArtifactDB,
                col(ArtifactDB.id) == col(ConversationShareArtifactDB.artifact_id),
            )
            .where(
                ConversationShareArtifactDB.share_id == share_id,
                ConversationShareArtifactDB.artifact_id == artifact_id,
            )
        )
        result = await self.db.execute(stmt)
        return cast(
            tuple[ConversationShareArtifactDB, ArtifactDB] | None,
            result.one_or_none(),
        )
