from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, Column, Enum as SAEnum, Integer, String, Text, text
from sqlmodel import Field, Index, UniqueConstraint

from app.models import BaseDBModel


class MemorySource(str, Enum):
    manual = "manual"
    assistant = "assistant"


class MemoryCategoryDB(BaseDBModel, table=True):
    __tablename__ = "memory_categories"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "normalized_name",
            name="uq_memory_categories_user_name",
        ),
        Index("ix_memory_categories_user_position", "user_id", "position"),
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    name: str = Field(sa_column=Column(String(100), nullable=False))
    normalized_name: str = Field(sa_column=Column(String(100), nullable=False))
    position: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )


class MemoryDB(BaseDBModel, table=True):
    __tablename__ = "memories"
    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "key",
            name="uq_memories_category_key",
        ),
        Index("ix_memories_user_updated", "user_id", "updated_at"),
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    category_id: UUID = Field(
        foreign_key="memory_categories.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    key: str = Field(sa_column=Column(String(100), nullable=False))
    title: str = Field(sa_column=Column(String(200), nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    source: MemorySource = Field(
        default=MemorySource.manual,
        sa_column=Column(
            SAEnum(
                MemorySource,
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
            server_default=MemorySource.manual.value,
        ),
    )
    source_thread_id: str | None = Field(
        default=None,
        foreign_key="threads.id",
        ondelete="SET NULL",
        nullable=True,
        index=True,
    )


class MemoryPreferenceDB(BaseDBModel, table=True):
    __tablename__ = "memory_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_memory_preferences_user_id"),
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    auto_capture_enabled: bool = Field(
        default=False,
        sa_column=Column(
            Boolean,
            nullable=False,
            server_default=text("false"),
        ),
    )
