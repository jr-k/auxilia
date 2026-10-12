"""Transactional outbox rows for workspace realtime invalidations."""

from uuid import UUID

from sqlalchemy import Column, Index
from sqlmodel import Field, String

from app.models import BaseDBModel


class WorkspaceEventOutboxDB(BaseDBModel, table=True):
    __tablename__ = "workspace_event_outbox"
    __table_args__ = (Index("ix_workspace_event_outbox_created_at", "created_at"),)

    workspace_id: UUID = Field(
        foreign_key="workspaces.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    target_user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        ondelete="CASCADE",
        nullable=True,
        index=True,
    )
    kind: str = Field(sa_column=Column(String(50), nullable=False))
    # Deliberately not a foreign key: a delete invalidation must survive the
    # thread row disappearing before the relay publishes it.
    thread_id: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
