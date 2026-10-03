from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.model_providers.models import ModelDB, ModelProviderCredentialDB
from app.repository import BaseRepository
from app.utils.encryption import decrypt_value, encrypt_value


class ModelRepository(BaseRepository[ModelDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(ModelDB, db)

    async def list_all(self) -> list[ModelDB]:
        stmt = select(ModelDB)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_provider_and_model_id(
        self, provider: str, model_id: str, *, for_update: bool = False
    ) -> ModelDB | None:
        stmt = select(ModelDB).where(
            ModelDB.provider == provider,
            ModelDB.model_id == model_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default(self, *, for_update: bool = False) -> ModelDB | None:
        stmt = select(ModelDB).where(ModelDB.is_default)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class ModelProviderCredentialRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_api_keys(self) -> dict[str, str]:
        stmt = select(ModelProviderCredentialDB)
        result = await self.db.execute(stmt)
        return {
            row.provider: decrypt_value(row.api_key_encrypted)
            for row in result.scalars().all()
        }

    async def get_api_key(self, provider: str) -> str | None:
        stmt = select(ModelProviderCredentialDB).where(
            ModelProviderCredentialDB.provider == provider
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return decrypt_value(row.api_key_encrypted) if row else None

    async def set_api_key(self, provider: str, api_key: str) -> None:
        stmt = select(ModelProviderCredentialDB).where(
            ModelProviderCredentialDB.provider == provider
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        encrypted = encrypt_value(api_key)
        if row is None:
            try:
                async with self.db.begin_nested():
                    row = ModelProviderCredentialDB(
                        provider=provider,
                        api_key_encrypted=encrypted,
                    )
                    self.db.add(row)
                    await self.db.flush()
            except IntegrityError:
                result = await self.db.execute(stmt)
                row = result.scalar_one()
                row.api_key_encrypted = encrypted
                self.db.add(row)
        else:
            row.api_key_encrypted = encrypted
            self.db.add(row)
        await self.db.flush()

    async def delete_api_key(self, provider: str) -> None:
        stmt = select(ModelProviderCredentialDB).where(
            ModelProviderCredentialDB.provider == provider
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            await self.db.delete(row)
        await self.db.flush()
