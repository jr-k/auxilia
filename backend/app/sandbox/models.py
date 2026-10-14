from enum import Enum
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Enum as SAEnum, Field, SQLModel

from app.models import BaseDBModel


class SandboxProviderType(str, Enum):
    opensandbox = "opensandbox"
    cloudrun = "cloudrun"
    daytona = "daytona"


class SandboxBase(SQLModel):
    """Shared shape of every sandbox: endpoint + provider + extras.

    `url` and the credential are first-class (every provider has exactly one
    of each); `config` holds only the provider-specific remainder plus the
    shared runtime knobs (default_packages, timeout), always validated through
    the typed union in schemas.py before it touches the row.
    """

    workspace_id: UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    name: str = Field(max_length=255, nullable=False)
    description: str | None = Field(default=None, max_length=255)
    provider: SandboxProviderType = Field(
        sa_column=Column(SAEnum(SandboxProviderType), nullable=False)
    )
    url: str = Field(nullable=False)
    config: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))


class SandboxDB(SandboxBase, BaseDBModel, table=True):
    __tablename__ = "sandboxes"

    encrypted_secret: str | None = Field(default=None)
    image_revision: UUID | None = Field(default=None, nullable=True)


class SandboxImageDB(BaseDBModel, table=True):
    __tablename__ = "sandbox_images"
    __table_args__ = (
        sa.UniqueConstraint("sandbox_id", name="uq_sandbox_image_sandbox_id"),
    )

    sandbox_id: UUID = Field(
        foreign_key="sandboxes.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    data: bytes = Field(sa_column=Column(sa.LargeBinary, nullable=False))
    media_type: str = Field(max_length=50, nullable=False)
    sha256: str = Field(max_length=64, nullable=False)
