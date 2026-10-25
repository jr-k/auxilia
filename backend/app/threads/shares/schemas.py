from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ConversationShareResponse(BaseModel):
    id: UUID
    thread_id: str
    token: str
    created_at: datetime | None


class PublicAgent(BaseModel):
    name: str
    emoji: str | None
    color: str | None


class PublicArtifact(BaseModel):
    id: UUID
    tool_call_id: str | None
    title: str
    filename: str
    mime_type: str
    size: int


class PublicConversationResponse(BaseModel):
    id: UUID
    title: str | None
    published_at: datetime | None
    agent: PublicAgent
    messages: list[dict[str, Any]]
    artifacts: list[PublicArtifact]
