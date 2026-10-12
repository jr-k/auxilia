from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Column, Enum as SAEnum, Field, SQLModel

from app.models import BaseDBModel


class DatabaseEngine(str, Enum):
    postgres = "postgres"
    mysql = "mysql"
    mariadb = "mariadb"
    sqlserver = "sqlserver"
    oracle = "oracle"


class DatabaseConnectionStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    error = "error"


class DatabaseConnectionBase(SQLModel):
    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    owner_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )
    mcp_server_id: UUID = Field(
        foreign_key="mcp_servers.id",
        ondelete="CASCADE",
        nullable=False,
        unique=True,
    )
    source_id: str = Field(max_length=64, nullable=False, unique=True)
    engine: DatabaseEngine = Field(
        sa_column=Column(
            SAEnum(DatabaseEngine, native_enum=False, create_constraint=False),
            nullable=False,
        )
    )
    host: str = Field(max_length=255, nullable=False)
    port: int = Field(nullable=False)
    database: str = Field(max_length=255, nullable=False)
    username: str = Field(max_length=255, nullable=False)
    ssl_mode: str | None = Field(default=None, max_length=64)
    connection_timeout: int = Field(default=10, ge=1, le=300)
    query_timeout: int = Field(default=30, ge=1, le=3600)
    readonly: bool = Field(default=True, nullable=False)
    max_rows: int = Field(default=500, ge=1, le=10000)


class DatabaseConnectionDB(DatabaseConnectionBase, BaseDBModel, table=True):
    __tablename__ = "database_connections"

    desired_revision: int = Field(default=1, nullable=False)
    applied_revision: int = Field(default=0, nullable=False)
    status: DatabaseConnectionStatus = Field(
        default=DatabaseConnectionStatus.pending,
        sa_column=Column(
            SAEnum(
                DatabaseConnectionStatus,
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
    )
    last_error: str | None = Field(default=None, max_length=1000)
    last_applied_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class DatabaseConnectionCredentialDB(BaseDBModel, table=True):
    __tablename__ = "database_connection_credentials"

    database_connection_id: UUID = Field(
        foreign_key="database_connections.id",
        ondelete="CASCADE",
        nullable=False,
        unique=True,
    )
    password_encrypted: str = Field(nullable=False)


class DBHubControlStateDB(BaseDBModel, table=True):
    __tablename__ = "dbhub_control_state"

    key: str = Field(default="global", max_length=32, nullable=False, unique=True)
    desired_revision: int = Field(default=0, nullable=False)
    applied_revision: int = Field(default=0, nullable=False)
    last_error: str | None = Field(default=None, max_length=1000)
    last_applied_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
