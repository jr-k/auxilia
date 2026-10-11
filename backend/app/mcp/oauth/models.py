from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field

from app.models import BaseDBModel


class MCPOAuthClientDB(BaseDBModel, table=True):
    __tablename__ = "mcp_oauth_clients"

    client_id: str = Field(max_length=255, nullable=False, unique=True, index=True)
    client_secret_encrypted: str | None = Field(
        default=None, sa_column=Column(sa.Text, nullable=True)
    )
    metadata_json: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=sa.text("'{}'")),
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(sa.DateTime(timezone=True), nullable=True),
    )


class MCPOAuthAuthorizationRequestDB(BaseDBModel, table=True):
    __tablename__ = "mcp_oauth_authorization_requests"

    handle_hash: str = Field(max_length=64, nullable=False, unique=True, index=True)
    client_id: str = Field(max_length=255, nullable=False, index=True)
    state: str | None = Field(default=None, sa_column=Column(sa.Text, nullable=True))
    scopes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=sa.text("'[]'")),
    )
    code_challenge: str = Field(max_length=255, nullable=False)
    redirect_uri: str = Field(sa_column=Column(sa.Text, nullable=False))
    redirect_uri_provided_explicitly: bool = Field(nullable=False)
    resource: str = Field(sa_column=Column(sa.Text, nullable=False))
    expires_at: datetime = Field(
        sa_column=Column(sa.DateTime(timezone=True), nullable=False, index=True)
    )
    status: str = Field(default="pending", max_length=16, nullable=False, index=True)
    user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        ondelete="CASCADE",
        nullable=True,
        index=True,
    )
    workspace_id: UUID | None = Field(
        default=None,
        foreign_key="workspaces.id",
        ondelete="CASCADE",
        nullable=True,
        index=True,
    )
    code_hash: str | None = Field(default=None, max_length=64, unique=True, index=True)


class MCPOAuthGrantDB(BaseDBModel, table=True):
    __tablename__ = "mcp_oauth_grants"

    client_id: str = Field(max_length=255, nullable=False, index=True)
    user_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )
    workspace_id: UUID = Field(
        foreign_key="workspaces.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    scopes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=sa.text("'[]'")),
    )
    resource: str = Field(sa_column=Column(sa.Text, nullable=False))
    access_token_hash: str = Field(
        max_length=64, nullable=False, unique=True, index=True
    )
    access_expires_at: datetime = Field(
        sa_column=Column(sa.DateTime(timezone=True), nullable=False, index=True)
    )
    refresh_token_hash: str = Field(
        max_length=64, nullable=False, unique=True, index=True
    )
    refresh_expires_at: datetime = Field(
        sa_column=Column(sa.DateTime(timezone=True), nullable=False, index=True)
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(sa.DateTime(timezone=True), nullable=True),
    )
