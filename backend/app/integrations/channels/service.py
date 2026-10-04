import json
import secrets
import string
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.service import AgentService
from app.agents.models import EffectivePermission
from app.agents.schemas import AgentListResponse
from app.database import AsyncSessionLocal
from app.exceptions import DomainValidationError, NotFoundError
from app.integrations.channels.repository import (
    ExternalActionRepository,
    ExternalConversationRepository,
    ExternalIdentityRepository,
)
from app.model_providers.service import ModelService
from app.notifications.models import (
    ExternalActionDB,
    ExternalConversationDB,
    ExternalIdentityDB,
    ExternalProvider,
)
from app.redis_client import get_redis
from app.runtime.runs.service import RunService
from app.threads.models import ThreadDB, ThreadSource
from app.threads.repository import ThreadRepository
from app.workspaces.repository import WorkspaceRepository


LINK_TTL_SECONDS = 600
LINK_PREFIX = "channel-link:"


def _source(provider: ExternalProvider) -> ThreadSource:
    return (
        ThreadSource.telegram
        if provider == ExternalProvider.telegram
        else ThreadSource.discord
    )


class ChannelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.identities = ExternalIdentityRepository(db)
        self.conversations = ExternalConversationRepository(db)
        self.actions = ExternalActionRepository(db)

    async def create_link_code(self, workspace_id: UUID, user_id: UUID) -> str:
        alphabet = string.ascii_uppercase + string.digits
        redis = get_redis()
        value = json.dumps({"workspace_id": str(workspace_id), "user_id": str(user_id)})
        for _ in range(8):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            if await redis.set(
                f"{LINK_PREFIX}{code}", value, ex=LINK_TTL_SECONDS, nx=True
            ):
                return code
        raise RuntimeError("Could not allocate a channel link code")

    async def consume_link_code(
        self,
        *,
        workspace_id: UUID,
        provider: ExternalProvider,
        external_user_id: str,
        display_name: str | None,
        code: str,
    ) -> ExternalIdentityDB:
        key = f"{LINK_PREFIX}{code.strip().upper()}"
        redis = get_redis()
        raw = await redis.get(key)
        if not raw:
            raise DomainValidationError("This link code is invalid or expired")
        payload = json.loads(raw)
        if payload.get("workspace_id") != str(workspace_id):
            raise DomainValidationError("This link code belongs to another workspace")
        if await redis.getdel(key) is None:
            raise DomainValidationError("This link code was already used")
        user_id = UUID(payload["user_id"])
        if (
            await WorkspaceRepository(self.db).get_membership(workspace_id, user_id)
            is None
        ):
            raise NotFoundError("Workspace membership not found")
        current = await self.identities.get_external(
            workspace_id, provider, external_user_id
        )
        if current is not None and current.user_id != user_id:
            raise DomainValidationError("This account is already linked")
        previous = await self.identities.get_for_user(workspace_id, provider, user_id)
        if previous is not None and previous.external_user_id != external_user_id:
            await self.conversations.delete_for_identity(
                workspace_id, provider, previous.external_user_id
            )
            await self.db.delete(previous)
            await self.db.flush()
        if current is None:
            current = ExternalIdentityDB(
                workspace_id=workspace_id,
                provider=provider,
                external_user_id=external_user_id,
                user_id=user_id,
                display_name=display_name,
            )
        else:
            current.display_name = display_name
        self.db.add(current)
        await self.db.flush()
        await self.db.refresh(current)
        return current

    async def unlink_identity(
        self,
        workspace_id: UUID,
        provider: ExternalProvider,
        user_id: UUID,
    ) -> None:
        identity = await self.identities.get_for_user(workspace_id, provider, user_id)
        if identity is None:
            return
        await self.conversations.delete_for_identity(
            workspace_id, provider, identity.external_user_id
        )
        await self.identities.unlink(workspace_id, provider, user_id)

    async def list_agents(
        self, workspace_id: UUID, identity: ExternalIdentityDB
    ) -> list[AgentListResponse]:
        membership = await WorkspaceRepository(self.db).get_membership(
            workspace_id, identity.user_id
        )
        if membership is None:
            return []
        agents = await AgentService(self.db, workspace_id).list(
            user_id=identity.user_id,
            user_role=membership.role,
            user_team_id=membership.team_id,
        )
        return sorted(
            (agent for agent in agents if agent.current_user_permission is not None),
            key=lambda agent: ((agent.name or "").lower(), str(agent.id)),
        )

    async def select_agent(
        self,
        *,
        workspace_id: UUID,
        identity: ExternalIdentityDB,
        provider: ExternalProvider,
        external_chat_id: str,
        external_thread_id: str = "",
        agent_id: UUID,
    ) -> ExternalConversationDB:
        membership = await WorkspaceRepository(self.db).get_membership(
            workspace_id, identity.user_id
        )
        if membership is None:
            raise NotFoundError("Workspace membership not found")
        await AgentService(self.db, workspace_id).require_permission(
            agent_id,
            user_id=identity.user_id,
            user_role=membership.role,
            user_team_id=membership.team_id,
            at_least=EffectivePermission.member,
            action="use this agent",
        )
        existing = await self.conversations.get_scope(
            workspace_id,
            provider,
            external_chat_id,
            external_thread_id,
            identity.external_user_id,
        )
        if existing is not None:
            await self.db.delete(existing)
            await self.db.flush()
        thread = ThreadDB(
            workspace_id=workspace_id,
            user_id=identity.user_id,
            agent_id=agent_id,
            model_id=await ModelService(self.db, workspace_id).get_default_model_id(),
            source=_source(provider),
        )
        self.db.add(thread)
        await self.db.flush()
        conversation = ExternalConversationDB(
            workspace_id=workspace_id,
            provider=provider,
            external_chat_id=external_chat_id,
            external_thread_id=external_thread_id,
            external_user_id=identity.external_user_id,
            thread_id=thread.id,
        )
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def enqueue_message(
        self,
        *,
        conversation: ExternalConversationDB,
        identity: ExternalIdentityDB,
        text: str,
        delivery: Mapping[str, object],
    ) -> None:
        thread = await ThreadRepository(self.db, conversation.workspace_id).get(
            conversation.thread_id
        )
        if thread is None:
            raise NotFoundError("Thread not found")
        membership = await WorkspaceRepository(self.db).get_membership(
            conversation.workspace_id, identity.user_id
        )
        if membership is None:
            raise NotFoundError("Workspace membership not found")
        await AgentService(self.db, conversation.workspace_id).require_permission(
            thread.agent_id,
            user_id=identity.user_id,
            user_role=membership.role,
            user_team_id=membership.team_id,
            at_least=EffectivePermission.member,
            action="use this agent",
        )
        if thread.first_message_content is None:
            thread.first_message_content = text
            self.db.add(thread)
            await self.db.flush()
        await self.db.commit()
        await RunService().create(
            thread_id=conversation.thread_id,
            user_id=str(identity.user_id),
            input={"messages": [{"type": "human", "content": text}]},
            delivery=dict(delivery),
        )

    async def create_actions(
        self,
        *,
        provider: ExternalProvider,
        workspace_id: UUID,
        user_id: UUID,
        thread_id: str,
        interrupt_id: str,
        requests: list[dict],
    ) -> list[ExternalActionDB]:
        expires_at = datetime.now(UTC) + timedelta(days=7)
        rows = [
            ExternalActionDB(
                provider=provider,
                workspace_id=workspace_id,
                user_id=user_id,
                thread_id=thread_id,
                interrupt_id=interrupt_id,
                tool_call_id=request["tool_call_id"],
                expires_at=expires_at,
            )
            for request in requests
        ]
        self.db.add_all(rows)
        await self.db.flush()
        for row in rows:
            await self.db.refresh(row)
        return rows

    async def decide_action(
        self,
        provider: ExternalProvider,
        token: str,
        decision: str,
        delivery: Mapping[str, object],
        actor_user_id: UUID,
    ) -> bool:
        if decision not in {"approve", "reject"}:
            raise DomainValidationError("Invalid approval decision")
        action = await self.actions.get_token(provider, token)
        if action is None:
            raise NotFoundError("Approval request not found")
        if action.user_id != actor_user_id:
            raise NotFoundError("Approval request not found")
        thread = await ThreadRepository(self.db, action.workspace_id).get(
            action.thread_id
        )
        membership = await WorkspaceRepository(self.db).get_membership(
            action.workspace_id, action.user_id
        )
        if thread is None or membership is None:
            raise NotFoundError("Approval request not found")
        await AgentService(self.db, action.workspace_id).require_permission(
            thread.agent_id,
            user_id=action.user_id,
            user_role=membership.role,
            user_team_id=membership.team_id,
            at_least=EffectivePermission.member,
            action="use this agent",
        )
        batch = await self.actions.list_interrupt(
            provider,
            action.thread_id,
            action.interrupt_id,
            for_update=True,
        )
        action = next((item for item in batch if item.token == token), None)
        if action is None:
            raise NotFoundError("Approval request not found")
        if action.decision is not None:
            return False
        action.decision = decision
        self.db.add(action)
        await self.db.flush()
        if not batch or any(item.decision is None for item in batch):
            await self.db.commit()
            return False
        command = {
            "resume": {
                "interrupt_id": action.interrupt_id,
                "decisions": [
                    {
                        "tool_call_id": item.tool_call_id,
                        "type": item.decision,
                    }
                    for item in batch
                ],
            }
        }
        await RunService().create_in_session(
            self.db,
            thread_id=action.thread_id,
            user_id=str(action.user_id),
            command=command,
            delivery=dict(delivery),
            multitask_strategy="enqueue",
        )
        await self.db.commit()
        return True


async def get_external_identity(
    workspace_id: UUID,
    provider: ExternalProvider,
    external_user_id: str,
) -> ExternalIdentityDB | None:
    async with AsyncSessionLocal() as db:
        return await ExternalIdentityRepository(db).get_external(
            workspace_id, provider, external_user_id
        )
