from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlmodel import SQLModel


class ConversationShareCreateDB(SQLModel):
    workspace_id: UUID
    thread_id: str
    created_by_id: UUID
    checkpoint_id: str
    title: str | None = None
    agent_name: str
    agent_emoji: str | None = None
    agent_color: str | None = None
    model_id: str | None = None
    model_name: str | None = None
    memories_enabled: bool | None = None
    cost: dict[str, Any] | None = None
    runs: list[dict[str, Any]]
    tool_servers: list[dict[str, Any]]


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


class PublicToolServer(BaseModel):
    name: str
    icon_url: str | None
    tool_names: list[str] = Field(default_factory=list)


class PublicConversationCost(BaseModel):
    known_cost: str
    complete: bool
    call_count: int
    unpriced_call_count: int
    total_tokens: int


class PublicRun(BaseModel):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    kind: str
    input_message_id: str | None


class PublicConversationResponse(BaseModel):
    id: UUID
    title: str | None
    published_at: datetime | None
    agent: PublicAgent
    model_id: str | None
    model_name: str | None
    memories_enabled: bool | None
    cost: PublicConversationCost | None
    runs: list[PublicRun]
    messages: list[dict[str, Any]]
    artifacts: list[PublicArtifact]
    tool_servers: list[PublicToolServer]
