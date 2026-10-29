from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import DomainValidationError, NotFoundError, PermissionDeniedError
from app.users.models import UserDB
from app.users.repository import UserRepository
from app.workspaces.repository import WorkspaceRepository


class SupervisionService:
    def __init__(self, db: AsyncSession):
        self.users = UserRepository(db)
        self.workspaces = WorkspaceRepository(db)

    async def resolve_target(
        self,
        *,
        actor_id: UUID,
        user_id: UUID,
        workspace_id: UUID,
    ) -> UserDB:
        if actor_id == user_id:
            raise DomainValidationError("You cannot supervise your own account")
        row = await self.users.get_in_workspace(user_id, workspace_id)
        if row is None:
            raise NotFoundError("User not found in this workspace")
        user, membership = row
        user.set_workspace_membership(membership)
        return user

    async def restore_actor(
        self,
        actor_id: UUID,
        preferred_workspace_id: UUID | None,
    ) -> UserDB:
        actor = await self.users.get(actor_id)
        if actor is None or not actor.is_instance_owner:
            raise PermissionDeniedError("Instance owner access required")

        membership = (
            await self.workspaces.get_membership(preferred_workspace_id, actor.id)
            if preferred_workspace_id is not None
            else None
        )
        membership = membership or await self.workspaces.get_first_membership(actor.id)
        if membership is not None:
            actor.set_workspace_membership(membership)
        return actor


def get_supervision_service(
    db: AsyncSession = Depends(get_db),
) -> SupervisionService:
    return SupervisionService(db)
