from uuid import UUID

from pydantic import BaseModel, Field

from app.visibility import ResourceVisibility


class SkillDocumentCreate(BaseModel):
    """MCP payload for a library-authored, single-file skill."""

    content: str = Field(min_length=1, max_length=110_000)
    group: str | None = None
    emoji: str | None = Field(default=None, max_length=10)
    color: str | None = Field(default=None, max_length=7)
    visibility: ResourceVisibility | None = None
    team_ids: list[UUID] | None = None
