from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.observability.models import WorkspaceObservabilityDB
from app.repository import BaseRepository
from app.utils.encryption import decrypt_value, encrypt_value


class WorkspaceObservabilityRepository(BaseRepository[WorkspaceObservabilityDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkspaceObservabilityDB, db)

    async def get_settings(self) -> WorkspaceObservabilityDB | None:
        stmt = select(WorkspaceObservabilityDB).where(
            WorkspaceObservabilityDB.key == "default"
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_credentials(self) -> tuple[str, str] | None:
        row = await self.get_settings()
        if (
            row is None
            or not row.enabled
            or not row.public_key_encrypted
            or not row.secret_key_encrypted
        ):
            return None
        return (
            decrypt_value(row.public_key_encrypted),
            decrypt_value(row.secret_key_encrypted),
        )

    async def save(
        self,
        *,
        enabled: bool,
        base_url: str,
        timeout_seconds: int,
        public_key: str | None,
        secret_key: str | None,
    ) -> WorkspaceObservabilityDB:
        row = await self.get_settings()
        if row is None:
            row = WorkspaceObservabilityDB()
        row.enabled = enabled
        row.base_url = base_url
        row.timeout_seconds = timeout_seconds
        if public_key is not None:
            row.public_key_encrypted = encrypt_value(public_key)
        if secret_key is not None:
            row.secret_key_encrypted = encrypt_value(secret_key)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def clear(self) -> None:
        row = await self.get_settings()
        if row is not None:
            await self.db.delete(row)
        await self.db.flush()
