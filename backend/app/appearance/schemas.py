from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceAppearanceResponse(BaseModel):
    app_name: str
    logo_revision: UUID | None = None


class WorkspaceAppearancePatch(BaseModel):
    app_name: str = Field(min_length=1, max_length=50)
