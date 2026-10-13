from datetime import datetime
from enum import Enum
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import BigInteger, DateTime
from sqlmodel import Column, Enum as SAEnum, Field, SQLModel

from app.models import BaseDBModel


class DatabaseEngine(str, Enum):
    sqlite = "sqlite"
    postgres = "postgres"
    mysql = "mysql"
    mariadb = "mariadb"
    sqlserver = "sqlserver"
    oracle = "oracle"


DATABASE_ENGINE_ICON_URLS: dict[DatabaseEngine, str] = {
    DatabaseEngine.sqlite: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/sqlite/sqlite-original.svg",
    DatabaseEngine.postgres: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/postgresql/postgresql-original.svg",
    DatabaseEngine.mysql: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/mysql/mysql-original.svg",
    DatabaseEngine.mariadb: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/mariadb/mariadb-original.svg",
    DatabaseEngine.sqlserver: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/microsoftsqlserver/microsoftsqlserver-original.svg",
    DatabaseEngine.oracle: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/oracle/oracle-original.svg",
}


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
    host: str | None = Field(default=None, max_length=255, nullable=True)
    port: int | None = Field(default=None, nullable=True)
    database: str = Field(max_length=255, nullable=False)
    username: str | None = Field(default=None, max_length=255, nullable=True)
    sqlite_file_id: UUID | None = Field(
        default=None,
        foreign_key="database_files.id",
        ondelete="RESTRICT",
        nullable=True,
        index=True,
    )
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

    @property
    def display_endpoint(self) -> str:
        if self.engine == DatabaseEngine.sqlite:
            return f"sqlite:///{quote(self.database, safe='')}"
        scheme = {
            DatabaseEngine.postgres: "postgresql",
            DatabaseEngine.mysql: "mysql",
            DatabaseEngine.mariadb: "mariadb",
            DatabaseEngine.sqlserver: "sqlserver",
            DatabaseEngine.oracle: "oracle",
        }[self.engine]
        assert self.host is not None
        assert self.port is not None
        assert self.username is not None
        host = (
            f"[{self.host}]"
            if ":" in self.host
            and not (self.host.startswith("[") and self.host.endswith("]"))
            else self.host
        )
        username = quote(self.username, safe="")
        database = quote(self.database, safe="")
        return f"{scheme}://{username}@{host}:{self.port}/{database}"


class DatabaseFileDB(BaseDBModel, table=True):
    __tablename__ = "database_files"

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    owner_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )
    original_name: str = Field(max_length=255, nullable=False)
    stored_name: str = Field(max_length=64, nullable=False, unique=True)
    size_bytes: int = Field(sa_column=Column(BigInteger, nullable=False))


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
