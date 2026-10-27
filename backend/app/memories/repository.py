from uuid import UUID

from sqlalchemy import func, or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.memories.models import (
    MemoryCategoryDB,
    MemoryDB,
    MemoryPreferenceDB,
    MemorySource,
)
from app.repository import BaseRepository


class MemoryCategoryRepository(BaseRepository[MemoryCategoryDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(MemoryCategoryDB, db)

    async def list_with_counts(
        self, user_id: UUID
    ) -> list[tuple[MemoryCategoryDB, int]]:
        stmt = (
            select(MemoryCategoryDB, func.count(col(MemoryDB.id)))
            .outerjoin(
                MemoryDB,
                col(MemoryDB.category_id) == col(MemoryCategoryDB.id),
            )
            .where(MemoryCategoryDB.user_id == user_id)
            .group_by(col(MemoryCategoryDB.id))
            .order_by(
                col(MemoryCategoryDB.position).asc(),
                col(MemoryCategoryDB.created_at).asc(),
            )
        )
        result = await self.db.execute(stmt)
        return [(category, count) for category, count in result.all()]

    async def get_for_user(
        self, category_id: UUID, user_id: UUID
    ) -> MemoryCategoryDB | None:
        stmt = select(MemoryCategoryDB).where(
            MemoryCategoryDB.id == category_id,
            MemoryCategoryDB.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_normalized_name(
        self, user_id: UUID, normalized_name: str
    ) -> MemoryCategoryDB | None:
        stmt = select(MemoryCategoryDB).where(
            MemoryCategoryDB.user_id == user_id,
            MemoryCategoryDB.normalized_name == normalized_name,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def next_position(self, user_id: UUID) -> int:
        stmt = select(func.coalesce(func.max(MemoryCategoryDB.position), -1)).where(
            MemoryCategoryDB.user_id == user_id
        )
        return int((await self.db.execute(stmt)).scalar_one()) + 1

    async def lock_order(self, user_id: UUID) -> None:
        stmt = select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(str(user_id), 0),
            )
        )
        await self.db.execute(stmt)

    async def set_order(self, user_id: UUID, category_ids: list[UUID]) -> None:
        for position, category_id in enumerate(category_ids):
            stmt = (
                update(MemoryCategoryDB)
                .where(
                    col(MemoryCategoryDB.id) == category_id,
                    col(MemoryCategoryDB.user_id) == user_id,
                )
                .values(position=position)
            )
            await self.db.execute(stmt)


class MemoryRepository(BaseRepository[MemoryDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(MemoryDB, db)

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        query: str | None = None,
        category_id: UUID | None = None,
        limit: int | None = None,
    ) -> list[tuple[MemoryDB, str]]:
        stmt = (
            select(MemoryDB, MemoryCategoryDB.name)
            .join(
                MemoryCategoryDB,
                col(MemoryDB.category_id) == col(MemoryCategoryDB.id),
            )
            .where(
                MemoryDB.user_id == user_id,
                MemoryCategoryDB.user_id == user_id,
            )
            .order_by(
                col(MemoryCategoryDB.position).asc(),
                col(MemoryDB.updated_at).desc(),
                col(MemoryDB.id),
            )
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if category_id is not None:
            stmt = stmt.where(MemoryDB.category_id == category_id)
        if query and (term := query.strip()):
            escape = "\\"
            escaped = (
                term.replace(escape, escape * 2)
                .replace("%", f"{escape}%")
                .replace("_", f"{escape}_")
            )
            pattern = f"%{escaped}%"
            stmt = stmt.where(
                or_(
                    col(MemoryDB.title).ilike(pattern, escape=escape),
                    col(MemoryDB.content).ilike(pattern, escape=escape),
                    col(MemoryDB.key).ilike(pattern, escape=escape),
                    col(MemoryCategoryDB.name).ilike(pattern, escape=escape),
                )
            )
        result = await self.db.execute(stmt)
        return [(memory, category_name) for memory, category_name in result.all()]

    async def list_recent_for_user(
        self, user_id: UUID, *, limit: int
    ) -> list[tuple[MemoryDB, str]]:
        stmt = (
            select(MemoryDB, MemoryCategoryDB.name)
            .join(
                MemoryCategoryDB,
                col(MemoryDB.category_id) == col(MemoryCategoryDB.id),
            )
            .where(
                MemoryDB.user_id == user_id,
                MemoryCategoryDB.user_id == user_id,
            )
            .order_by(col(MemoryDB.updated_at).desc(), col(MemoryDB.id))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [(memory, category_name) for memory, category_name in result.all()]

    async def get_for_user(self, memory_id: UUID, user_id: UUID) -> MemoryDB | None:
        stmt = select(MemoryDB).where(
            MemoryDB.id == memory_id,
            MemoryDB.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_category_key(
        self, user_id: UUID, category_id: UUID, key: str
    ) -> MemoryDB | None:
        stmt = select(MemoryDB).where(
            MemoryDB.user_id == user_id,
            MemoryDB.category_id == category_id,
            MemoryDB.key == key,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_assistant(
        self,
        *,
        user_id: UUID,
        category_id: UUID,
        key: str,
        title: str,
        content: str,
        source_thread_id: str,
    ) -> MemoryDB:
        insert_stmt = pg_insert(MemoryDB).values(
            user_id=user_id,
            category_id=category_id,
            key=key,
            title=title,
            content=content,
            source=MemorySource.assistant,
            source_thread_id=source_thread_id,
        )
        stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_memories_category_key",
            set_={
                "title": insert_stmt.excluded.title,
                "content": insert_stmt.excluded.content,
                "source": MemorySource.assistant,
                "source_thread_id": insert_stmt.excluded.source_thread_id,
                "updated_at": func.now(),
            },
        ).returning(MemoryDB)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def list_by_ids(
        self, user_id: UUID, memory_ids: list[UUID]
    ) -> list[tuple[MemoryDB, str]]:
        if not memory_ids:
            return []
        stmt = (
            select(MemoryDB, MemoryCategoryDB.name)
            .join(
                MemoryCategoryDB,
                col(MemoryDB.category_id) == col(MemoryCategoryDB.id),
            )
            .where(
                MemoryDB.user_id == user_id,
                col(MemoryDB.id).in_(memory_ids),
            )
        )
        result = await self.db.execute(stmt)
        rows = list(result.all())
        by_id = {memory.id: (memory, category_name) for memory, category_name in rows}
        return [by_id[memory_id] for memory_id in memory_ids if memory_id in by_id]


class MemoryPreferenceRepository(BaseRepository[MemoryPreferenceDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(MemoryPreferenceDB, db)

    async def get_for_user(self, user_id: UUID) -> MemoryPreferenceDB | None:
        stmt = select(MemoryPreferenceDB).where(MemoryPreferenceDB.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def lock_for_user(self, user_id: UUID) -> MemoryPreferenceDB | None:
        stmt = (
            select(MemoryPreferenceDB)
            .where(MemoryPreferenceDB.user_id == user_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_auto_capture(
        self, user_id: UUID, enabled: bool
    ) -> MemoryPreferenceDB:
        insert_stmt = pg_insert(MemoryPreferenceDB).values(
            user_id=user_id,
            auto_capture_enabled=enabled,
        )
        stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_memory_preferences_user_id",
            set_={
                "auto_capture_enabled": enabled,
                "updated_at": func.now(),
            },
        ).returning(MemoryPreferenceDB)
        result = await self.db.execute(stmt)
        return result.scalar_one()
