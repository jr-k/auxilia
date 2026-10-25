import base64
import hashlib
import hmac
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.repository import AgentRepository
from app.artifacts.models import ArtifactDB
from app.artifacts.repository import ArtifactRepository
from app.artifacts.service import ArtifactGoneError, ArtifactService
from app.auth.settings import auth_settings
from app.database import get_checkpointer, get_db
from app.exceptions import DomainValidationError, NotFoundError, PermissionDeniedError
from app.runtime.checkpoints import checkpoint_thread_id, get_checkpoint_state
from app.runtime.hitl import pending_interrupt
from app.runtime.protocol.messages import serialize_public_message
from app.runtime.runs.repository import RunRepository
from app.threads.repository import ThreadRepository
from app.threads.shares.models import (
    ConversationShareArtifactDB,
    ConversationShareDB,
)
from app.threads.shares.repository import ConversationShareRepository
from app.threads.shares.schemas import (
    ConversationShareCreateDB,
    ConversationShareResponse,
    PublicAgent,
    PublicArtifact,
    PublicConversationResponse,
)


def _share_token(share_id: UUID) -> str:
    digest = hmac.new(
        auth_settings.JWT_SECRET_KEY.encode(),
        f"conversation-share:{share_id}".encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _referenced_artifact_ids(messages: list[Any]) -> list[UUID]:
    found: dict[UUID, None] = {}
    for message in messages:
        kwargs = getattr(message, "additional_kwargs", {}) or {}
        attachments = kwargs.get("attachments")
        if isinstance(attachments, list):
            for item in attachments:
                value = item if isinstance(item, str) else None
                if isinstance(item, dict):
                    value = item.get("id")
                try:
                    if isinstance(value, str):
                        found[UUID(value)] = None
                except ValueError:
                    continue

        artifact = getattr(message, "artifact", None)
        descriptors = (
            artifact.get("auxilia_artifacts") if isinstance(artifact, dict) else None
        )
        if isinstance(descriptors, list):
            for descriptor in descriptors:
                value = descriptor.get("id") if isinstance(descriptor, dict) else None
                try:
                    if isinstance(value, str):
                        found[UUID(value)] = None
                except ValueError:
                    continue
    return list(found)


def _share_response(share: ConversationShareDB) -> ConversationShareResponse:
    return ConversationShareResponse(
        id=share.id,
        thread_id=share.thread_id,
        token=_share_token(share.id),
        created_at=share.created_at,
    )


class ConversationShareService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ConversationShareRepository(db)

    async def _owned_thread(self, workspace_id: UUID, thread_id: str, user_id: UUID):
        thread = await ThreadRepository(self.db, workspace_id).get(thread_id)
        if thread is None:
            raise NotFoundError("Thread not found")
        if thread.user_id != user_id:
            raise PermissionDeniedError("Only the thread owner can publish it")
        return thread

    async def get(
        self, workspace_id: UUID, thread_id: str, user_id: UUID
    ) -> ConversationShareResponse | None:
        await self._owned_thread(workspace_id, thread_id, user_id)
        share = await self.repository.get_for_thread(workspace_id, thread_id)
        return _share_response(share) if share else None

    async def create(
        self, workspace_id: UUID, thread_id: str, user_id: UUID
    ) -> ConversationShareResponse:
        thread = await self._owned_thread(workspace_id, thread_id, user_id)
        runs = RunRepository(self.db, workspace_id)
        await runs.lock_thread_runs(thread_id)
        existing = await self.repository.get_for_thread(workspace_id, thread_id)
        if existing is not None:
            return _share_response(existing)
        locked_thread = await ThreadRepository(self.db, workspace_id).lock(thread_id)
        if locked_thread is None:
            raise NotFoundError("Thread not found")
        thread = locked_thread
        if await runs.get_active_for_thread(thread_id) is not None:
            raise DomainValidationError(
                "Wait for the conversation to finish before publishing it"
            )
        internal_thread_id = checkpoint_thread_id(workspace_id, thread_id)
        async with get_checkpointer() as checkpointer:
            state = await get_checkpoint_state(checkpointer, internal_thread_id)
        if state.saved is None or not state.messages:
            raise DomainValidationError("This conversation has no messages to publish")
        if pending_interrupt(state) is not None:
            raise DomainValidationError(
                "Resolve the pending approval before publishing this conversation"
            )
        visible_messages = [
            message
            for message in state.messages
            if serialize_public_message(message) is not None
        ]
        if not visible_messages:
            raise DomainValidationError(
                "This conversation has no visible messages to publish"
            )
        checkpoint_id = str(state.saved.checkpoint["id"])
        agent = await AgentRepository(self.db, workspace_id).get_scoped(thread.agent_id)
        if agent is None:
            raise NotFoundError("Agent not found")
        share = await self.repository.create(
            ConversationShareCreateDB(
                workspace_id=workspace_id,
                thread_id=thread_id,
                created_by_id=user_id,
                checkpoint_id=checkpoint_id,
                title=thread.first_message_content,
                agent_name=agent.name,
                agent_emoji=agent.emoji,
                agent_color=agent.color,
            )
        )

        artifact_ids = _referenced_artifact_ids(visible_messages)
        artifacts = await ArtifactRepository(self.db, workspace_id).by_ids(
            thread.id, artifact_ids
        )
        await self.repository.add_artifacts(
            [
                ConversationShareArtifactDB(
                    share_id=share.id,
                    artifact_id=row.id,
                    sha256=row.sha256,
                    origin=row.origin,
                    tool_call_id=row.tool_call_id,
                    title=row.title,
                    filename=row.filename,
                    mime_type=row.mime_type,
                    size=row.size,
                )
                for row in artifacts
            ]
        )
        return _share_response(share)

    async def delete(self, workspace_id: UUID, thread_id: str, user_id: UUID) -> None:
        await self._owned_thread(workspace_id, thread_id, user_id)
        share = await self.repository.get_for_thread(workspace_id, thread_id)
        if share is not None:
            await self.repository.delete(share)

    async def _resolve(self, share_id: UUID, token: str):
        row = await self.repository.public_details(share_id)
        if row is None or not hmac.compare_digest(token, _share_token(share_id)):
            raise NotFoundError("Public conversation not found")
        return row

    async def public_snapshot(
        self, share_id: UUID, token: str
    ) -> PublicConversationResponse:
        share = await self._resolve(share_id, token)
        internal_thread_id = checkpoint_thread_id(share.workspace_id, share.thread_id)
        async with get_checkpointer() as checkpointer:
            state = await get_checkpoint_state(
                checkpointer,
                internal_thread_id,
                checkpoint_id=share.checkpoint_id,
            )
        if state.saved is None:
            raise NotFoundError("Public conversation is no longer available")
        messages = [
            serialized
            for message in state.messages
            if (serialized := serialize_public_message(message)) is not None
        ]
        artifacts = await self.repository.list_artifacts(share.id)
        return PublicConversationResponse(
            id=share.id,
            title=share.title,
            published_at=share.created_at,
            agent=PublicAgent(
                name=share.agent_name,
                emoji=share.agent_emoji,
                color=share.agent_color,
            ),
            messages=messages,
            artifacts=[
                PublicArtifact(
                    id=item.artifact_id,
                    tool_call_id=item.tool_call_id,
                    title=item.title,
                    filename=item.filename,
                    mime_type=item.mime_type,
                    size=item.size,
                )
                for item in artifacts
            ],
        )

    async def public_artifact(
        self, share_id: UUID, artifact_id: UUID, token: str
    ) -> tuple[ArtifactDB, bytes]:
        share = await self._resolve(share_id, token)
        entry = await self.repository.artifact(share.id, artifact_id)
        if entry is None:
            raise NotFoundError("Shared file not found")
        snapshot, current = entry
        if (
            current.workspace_id != share.workspace_id
            or current.thread_id != share.thread_id
        ):
            raise NotFoundError("Shared file not found")
        if not hmac.compare_digest(snapshot.sha256, current.sha256):
            raise ArtifactGoneError("This shared file has changed since publication")
        return await ArtifactService(self.db, share.workspace_id).content(
            share.thread_id, artifact_id
        )


def get_conversation_share_service(
    db: AsyncSession = Depends(get_db),
) -> ConversationShareService:
    return ConversationShareService(db)
