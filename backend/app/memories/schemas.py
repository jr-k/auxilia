from datetime import datetime
from uuid import UUID

from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel

from app.memories.models import MemorySource


class MemoryCategoryCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)


class MemoryCategoryCreateDB(MemoryCategoryCreate):
    user_id: UUID
    normalized_name: str = Field(max_length=100)
    position: int = 0


class MemoryCategoryPatch(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class MemoryCategoryOrder(SQLModel):
    category_ids: list[UUID] = PydanticField(min_length=0)


class MemoryCategoryResponse(SQLModel):
    id: UUID
    name: str
    position: int
    memory_count: int = 0
    created_at: datetime
    updated_at: datetime


class MemoryCreate(SQLModel):
    category_id: UUID
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10_000)


class MemoryCreateDB(SQLModel):
    user_id: UUID
    category_id: UUID
    key: str = Field(max_length=100)
    title: str = Field(max_length=200)
    content: str = Field(max_length=10_000)
    source: MemorySource = MemorySource.manual
    source_thread_id: str | None = None


class MemoryPatch(SQLModel):
    category_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=10_000)


class MemoryResponse(SQLModel):
    id: UUID
    category_id: UUID
    category_name: str
    key: str
    title: str
    content: str
    source: MemorySource
    source_thread_id: str | None
    created_at: datetime
    updated_at: datetime


class MemoryCategoryGroup(MemoryCategoryResponse):
    memories: list[MemoryResponse] = Field(default_factory=list)


class MemoryLibraryResponse(SQLModel):
    categories: list[MemoryCategoryGroup] = Field(default_factory=list)
    total: int = 0


class MemoryPreferencesPatch(SQLModel):
    auto_capture_enabled: bool


class MemoryPreferencesResponse(SQLModel):
    auto_capture_enabled: bool = False
