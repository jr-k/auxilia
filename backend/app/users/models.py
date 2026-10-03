from enum import Enum
from uuid import UUID

from sqlalchemy import JSON, Column, LargeBinary, String
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.models import BaseDBModel


class WorkspaceRole(str, Enum):
    member = "member"
    editor = "editor"
    admin = "admin"


class UserBase(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255, unique=True, index=True)
    password_hash: str | None = Field(default=None)
    role: WorkspaceRole = Field(default=WorkspaceRole.member, nullable=False)
    picture_url: str | None = Field(default=None, max_length=1024)
    image_revision: UUID | None = Field(default=None, nullable=True)
    two_factor_enabled: bool = Field(default=False, nullable=False)


class UserDB(UserBase, BaseDBModel, table=True):
    __tablename__ = "users"

    team_id: UUID | None = Field(
        default=None,
        foreign_key="teams.id",
        ondelete="SET NULL",
        nullable=True,
    )

    oauth_accounts: list["OAuthAccountDB"] = Relationship(back_populates="user")


class UserImageDB(BaseDBModel, table=True):
    __tablename__ = "user_images"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_image_user_id"),)

    user_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )
    data: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    media_type: str = Field(max_length=50, nullable=False)
    sha256: str = Field(max_length=64, nullable=False)


class UserTwoFactorDB(BaseDBModel, table=True):
    __tablename__ = "user_two_factors"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_two_factor_user_id"),)

    user_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )
    secret_encrypted: str = Field(sa_column=Column(String, nullable=False))
    backup_code_hashes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )


class OAuthAccountBase(SQLModel):
    provider: str = Field(index=True)
    sub_id: str = Field(index=True)


class OAuthAccountDB(OAuthAccountBase, BaseDBModel, table=True):
    __tablename__ = "oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "sub_id"),)

    user_id: UUID = Field(foreign_key="users.id", nullable=False)

    user: UserDB = Relationship(back_populates="oauth_accounts")
