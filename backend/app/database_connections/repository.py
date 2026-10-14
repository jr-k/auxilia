from collections.abc import Collection
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.database_connections.models import (
    DatabaseConnectionCredentialDB,
    DatabaseConnectionDB,
    DatabaseFileDB,
    DBHubControlStateDB,
)
from app.repository import BaseRepository
from app.utils.encryption import decrypt_value, encrypt_value


DBHUB_RECONCILE_PENDING = "GeneratedConfigPending"


class DatabaseConnectionRepository(BaseRepository[DatabaseConnectionDB]):
    def __init__(self, db: AsyncSession, workspace_id: UUID | None = None):
        super().__init__(DatabaseConnectionDB, db)
        self.workspace_id = workspace_id

    def _scope(self, stmt):
        if self.workspace_id is not None:
            return stmt.where(DatabaseConnectionDB.workspace_id == self.workspace_id)
        return stmt

    async def list_scoped(self) -> list[DatabaseConnectionDB]:
        stmt = self._scope(select(DatabaseConnectionDB)).order_by(
            DatabaseConnectionDB.created_at
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[DatabaseConnectionDB]:
        stmt = select(DatabaseConnectionDB).order_by(DatabaseConnectionDB.source_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_ids(
        self, connection_ids: Collection[UUID]
    ) -> list[DatabaseConnectionDB]:
        if not connection_ids:
            return []
        stmt = self._scope(
            select(DatabaseConnectionDB).where(
                col(DatabaseConnectionDB.id).in_(connection_ids)
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def exists_in_workspace(self, workspace_id: UUID) -> bool:
        stmt = (
            select(DatabaseConnectionDB.id)
            .where(DatabaseConnectionDB.workspace_id == workspace_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_scoped(
        self, connection_id: UUID, *, for_update: bool = False
    ) -> DatabaseConnectionDB | None:
        stmt = self._scope(
            select(DatabaseConnectionDB).where(DatabaseConnectionDB.id == connection_id)
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_mcp_server(
        self, mcp_server_id: UUID
    ) -> DatabaseConnectionDB | None:
        stmt = self._scope(
            select(DatabaseConnectionDB).where(
                DatabaseConnectionDB.mcp_server_id == mcp_server_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_password(self, connection_id: UUID, password: str) -> None:
        stmt = select(DatabaseConnectionCredentialDB).where(
            DatabaseConnectionCredentialDB.database_connection_id == connection_id
        )
        result = await self.db.execute(stmt)
        credential = result.scalar_one_or_none()
        encrypted = encrypt_value(password)
        if credential is None:
            credential = DatabaseConnectionCredentialDB(
                database_connection_id=connection_id,
                password_encrypted=encrypted,
            )
        else:
            credential.password_encrypted = encrypted
        self.db.add(credential)
        await self.db.flush()

    async def get_password(self, connection_id: UUID) -> str | None:
        stmt = select(DatabaseConnectionCredentialDB.password_encrypted).where(
            DatabaseConnectionCredentialDB.database_connection_id == connection_id
        )
        result = await self.db.execute(stmt)
        encrypted = result.scalar_one_or_none()
        return decrypt_value(encrypted) if encrypted is not None else None

    async def delete_password(self, connection_id: UUID) -> None:
        stmt = delete(DatabaseConnectionCredentialDB).where(
            col(DatabaseConnectionCredentialDB.database_connection_id) == connection_id
        )
        await self.db.execute(stmt)

    async def get_control_state(
        self, *, for_update: bool = False
    ) -> DBHubControlStateDB:
        stmt = select(DBHubControlStateDB).where(DBHubControlStateDB.key == "global")
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()
        if state is None:
            state = DBHubControlStateDB(key="global")
            self.db.add(state)
            await self.db.flush()
        return state

    async def bump_desired_revision(self) -> int:
        state = await self.get_control_state(for_update=True)
        state.desired_revision += 1
        # New reconcilers use this marker as pending work. Mirroring the global
        # applied revision fences older replicas during a rolling upgrade:
        # their legacy loop sees an equal pair and cannot rewrite the former
        # unrestricted single-source topology.
        state.applied_revision = state.desired_revision
        state.last_error = DBHUB_RECONCILE_PENDING
        self.db.add(state)
        await self.db.flush()
        return state.desired_revision


class DatabaseFileRepository(BaseRepository[DatabaseFileDB]):
    def __init__(self, db: AsyncSession, workspace_id: UUID | None = None):
        super().__init__(DatabaseFileDB, db)
        self.workspace_id = workspace_id

    async def get_scoped(self, file_id: UUID) -> DatabaseFileDB | None:
        stmt = select(DatabaseFileDB).where(DatabaseFileDB.id == file_id)
        if self.workspace_id is not None:
            stmt = stmt.where(DatabaseFileDB.workspace_id == self.workspace_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_stored_names(self) -> set[str]:
        stmt = select(DatabaseFileDB.stored_name)
        result = await self.db.execute(stmt)
        return set(result.scalars().all())

    async def is_referenced(self, file_id: UUID) -> bool:
        stmt = (
            select(DatabaseConnectionDB.id)
            .where(DatabaseConnectionDB.sqlite_file_id == file_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
