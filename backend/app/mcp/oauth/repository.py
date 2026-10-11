from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.mcp.oauth.models import (
    MCPOAuthAuthorizationRequestDB,
    MCPOAuthClientDB,
    MCPOAuthGrantDB,
)
from app.workspaces.models import WorkspaceMembershipDB


class MCPOAuthRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_client(self, client_id: str) -> MCPOAuthClientDB | None:
        stmt = select(MCPOAuthClientDB).where(
            MCPOAuthClientDB.client_id == client_id,
            col(MCPOAuthClientDB.revoked_at).is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_client(self, client: MCPOAuthClientDB) -> None:
        self.db.add(client)
        await self.db.flush()

    async def create_authorization_request(
        self, request: MCPOAuthAuthorizationRequestDB
    ) -> None:
        self.db.add(request)
        await self.db.flush()

    async def get_authorization_request(
        self, handle_hash: str, *, for_update: bool = False
    ) -> MCPOAuthAuthorizationRequestDB | None:
        stmt = select(MCPOAuthAuthorizationRequestDB).where(
            MCPOAuthAuthorizationRequestDB.handle_hash == handle_hash
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_authorization_code(
        self, code_hash: str, *, for_update: bool = False
    ) -> MCPOAuthAuthorizationRequestDB | None:
        stmt = select(MCPOAuthAuthorizationRequestDB).where(
            MCPOAuthAuthorizationRequestDB.code_hash == code_hash
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_grant(self, grant: MCPOAuthGrantDB) -> None:
        self.db.add(grant)
        await self.db.flush()
        await self.db.refresh(grant)

    async def get_access_grant(
        self, token_hash: str, *, for_update: bool = False
    ) -> MCPOAuthGrantDB | None:
        stmt = select(MCPOAuthGrantDB).where(
            MCPOAuthGrantDB.access_token_hash == token_hash
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_refresh_grant(
        self, token_hash: str, *, for_update: bool = False
    ) -> MCPOAuthGrantDB | None:
        stmt = select(MCPOAuthGrantDB).where(
            MCPOAuthGrantDB.refresh_token_hash == token_hash
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_grant_for_update(self, grant_id: UUID) -> MCPOAuthGrantDB | None:
        stmt = (
            select(MCPOAuthGrantDB)
            .where(MCPOAuthGrantDB.id == grant_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def has_membership(self, workspace_id: UUID, user_id: UUID) -> bool:
        stmt = select(WorkspaceMembershipDB.id).where(
            WorkspaceMembershipDB.workspace_id == workspace_id,
            WorkspaceMembershipDB.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
