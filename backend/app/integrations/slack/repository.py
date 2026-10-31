from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.integrations.slack.db_models import (
    AgentSlackBotDB,
    SlackIdentityDB,
    SlackThreadBindingDB,
)
from app.repository import BaseRepository


class AgentSlackBotRepository(BaseRepository[AgentSlackBotDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentSlackBotDB, db)

    async def list_for_agent(
        self, workspace_id: UUID, agent_id: UUID
    ) -> list[AgentSlackBotDB]:
        stmt = (
            select(AgentSlackBotDB)
            .where(
                AgentSlackBotDB.workspace_id == workspace_id,
                AgentSlackBotDB.agent_id == agent_id,
            )
            .order_by(col(AgentSlackBotDB.created_at), col(AgentSlackBotDB.id))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_for_workspace(self, workspace_id: UUID) -> list[AgentSlackBotDB]:
        stmt = (
            select(AgentSlackBotDB)
            .where(AgentSlackBotDB.workspace_id == workspace_id)
            .order_by(col(AgentSlackBotDB.created_at), col(AgentSlackBotDB.id))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_for_agent(
        self, workspace_id: UUID, agent_id: UUID, bot_id: UUID
    ) -> AgentSlackBotDB | None:
        stmt = select(AgentSlackBotDB).where(
            AgentSlackBotDB.id == bot_id,
            AgentSlackBotDB.workspace_id == workspace_id,
            AgentSlackBotDB.agent_id == agent_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_runtime(self, bot_id: UUID) -> AgentSlackBotDB | None:
        stmt = select(AgentSlackBotDB).where(AgentSlackBotDB.id == bot_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_installation(
        self, slack_team_id: str, bot_user_id: str
    ) -> AgentSlackBotDB | None:
        stmt = select(AgentSlackBotDB).where(
            AgentSlackBotDB.slack_team_id == slack_team_id,
            AgentSlackBotDB.bot_user_id == bot_user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class SlackIdentityRepository(BaseRepository[SlackIdentityDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(SlackIdentityDB, db)

    async def get_external(
        self, workspace_id: UUID, slack_team_id: str, slack_user_id: str
    ) -> SlackIdentityDB | None:
        stmt = select(SlackIdentityDB).where(
            SlackIdentityDB.workspace_id == workspace_id,
            SlackIdentityDB.slack_team_id == slack_team_id,
            SlackIdentityDB.slack_user_id == slack_user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> list[SlackIdentityDB]:
        stmt = (
            select(SlackIdentityDB)
            .where(
                SlackIdentityDB.workspace_id == workspace_id,
                SlackIdentityDB.user_id == user_id,
            )
            .order_by(col(SlackIdentityDB.created_at), col(SlackIdentityDB.id))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_internal(
        self, workspace_id: UUID, slack_team_id: str, user_id: UUID
    ) -> SlackIdentityDB | None:
        stmt = select(SlackIdentityDB).where(
            SlackIdentityDB.workspace_id == workspace_id,
            SlackIdentityDB.slack_team_id == slack_team_id,
            SlackIdentityDB.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def unlink_user(self, workspace_id: UUID, user_id: UUID) -> None:
        stmt = delete(SlackIdentityDB).where(
            col(SlackIdentityDB.workspace_id) == workspace_id,
            col(SlackIdentityDB.user_id) == user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def unlink_team_user(
        self, workspace_id: UUID, slack_team_id: str, user_id: UUID
    ) -> None:
        stmt = delete(SlackIdentityDB).where(
            col(SlackIdentityDB.workspace_id) == workspace_id,
            col(SlackIdentityDB.slack_team_id) == slack_team_id,
            col(SlackIdentityDB.user_id) == user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()


class SlackThreadBindingRepository(BaseRepository[SlackThreadBindingDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(SlackThreadBindingDB, db)

    async def get_external(
        self, slack_bot_id: UUID, channel_id: str, slack_thread_ts: str
    ) -> SlackThreadBindingDB | None:
        stmt = select(SlackThreadBindingDB).where(
            SlackThreadBindingDB.slack_bot_id == slack_bot_id,
            SlackThreadBindingDB.channel_id == channel_id,
            SlackThreadBindingDB.slack_thread_ts == slack_thread_ts,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_thread(self, thread_id: str) -> SlackThreadBindingDB | None:
        stmt = select(SlackThreadBindingDB).where(
            SlackThreadBindingDB.thread_id == thread_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_for_identity(
        self, slack_bot_ids: list[UUID], slack_user_id: str
    ) -> None:
        if not slack_bot_ids:
            return
        stmt = delete(SlackThreadBindingDB).where(
            col(SlackThreadBindingDB.slack_bot_id).in_(slack_bot_ids),
            col(SlackThreadBindingDB.slack_user_id) == slack_user_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def mark_context_synced(self, binding_id: UUID, message_ts: str) -> None:
        binding = await self.get(binding_id)
        if binding is None:
            return
        binding.last_context_ts = message_ts
        self.db.add(binding)
        await self.db.flush()
