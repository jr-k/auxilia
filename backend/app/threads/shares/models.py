from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models import BaseDBModel, TimestampMixin


class ConversationShareDB(BaseDBModel, table=True):
    __tablename__ = "conversation_shares"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "thread_id",
            name="uq_conversation_shares_workspace_thread",
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    thread_id: str = Field(
        foreign_key="threads.id", ondelete="CASCADE", nullable=False, index=True
    )
    created_by_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False
    )
    checkpoint_id: str
    title: str | None = None
    agent_name: str
    agent_emoji: str | None = None
    agent_color: str | None = None


class ConversationShareArtifactDB(TimestampMixin, SQLModel, table=True):
    __tablename__ = "conversation_share_artifacts"

    share_id: UUID = Field(
        foreign_key="conversation_shares.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    artifact_id: UUID = Field(
        foreign_key="artifacts.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    sha256: str
    origin: str
    tool_call_id: str | None = None
    title: str
    filename: str
    mime_type: str
    size: int
