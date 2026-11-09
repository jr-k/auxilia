from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints
from sqlmodel import Field, SQLModel


class LangfuseStatusResponse(SQLModel):
    enabled: bool


class LangfusePromptVersion(SQLModel):
    version: int
    labels: list[str]
    commit_message: str | None = None
    text: str
    author: str | None = None
    created_at: datetime | None = None
    # Used for no-op detection, but server-owned metadata is never exposed.
    public_config: dict | None = Field(default=None, exclude=True)


class LangfusePromptResponse(SQLModel):
    production: LangfusePromptVersion | None
    diverged: bool


class LangfusePublishDraft(SQLModel):
    config_json: str
    labels: list[str]


class LangfusePublishRequest(SQLModel):
    commit_message: str | None = None
    label: Annotated[str, StringConstraints(min_length=1, pattern=r"^\S+$")] = (
        "production"
    )
    # JSON remains text so arbitrary config keys bypass API case conversion.
    config_json: str | None = None
