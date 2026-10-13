from uuid import UUID, uuid4

from fastapi import Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.mcp_servers.service import AgentMCPServerService
from app.database import get_db
from app.database_connections.client import list_dbhub_source_ids
from app.database_connections.files import store_sqlite_upload
from app.database_connections.models import (
    DATABASE_ENGINE_ICON_URLS,
    DatabaseConnectionDB,
    DatabaseConnectionStatus,
    DatabaseEngine,
    DatabaseFileDB,
)
from app.database_connections.repository import (
    DatabaseConnectionRepository,
    DatabaseFileRepository,
)
from app.database_connections.schemas import (
    DatabaseConnectionCreate,
    DatabaseConnectionPatch,
    DatabaseConnectionResponse,
    DatabaseConnectorStatusResponse,
    DatabaseFileCreateDB,
    SQLiteFileResponse,
)
from app.database_connections.settings import dbhub_settings
from app.database_connections.tools import (
    DBHUB_MANAGED_BY,
    allowed_tool_names,
    source_id_for_connection,
)
from app.exceptions import DomainValidationError, NotFoundError
from app.mcp.servers.models import MCPAuthType
from app.mcp.servers.schemas import MCPServerCreate, MCPServerPatch
from app.mcp.servers.service import MCPServerService
from app.service import BaseService
from app.users.models import UserDB
from app.workspaces.dependencies import get_active_workspace_id


def _public_connection_error(error: str | None) -> str | None:
    if error == "DBHub could not connect to this source":
        return "Could not connect to the database"
    if error == "DBHub did not apply this source":
        return "The database connection could not be configured"
    return error


class DatabaseConnectionService(
    BaseService[DatabaseConnectionDB, DatabaseConnectionRepository]
):
    not_found_message = "Database connection not found"

    def __init__(self, db: AsyncSession, workspace_id: UUID):
        super().__init__(db, DatabaseConnectionRepository(db, workspace_id))
        self.workspace_id = workspace_id
        self.mcp_servers = MCPServerService(db, workspace_id)
        self.files = DatabaseFileRepository(db, workspace_id)

    async def get_scoped(
        self, connection_id: UUID, *, for_update: bool = False
    ) -> DatabaseConnectionDB:
        connection = await self.repository.get_scoped(
            connection_id, for_update=for_update
        )
        if connection is None:
            raise NotFoundError(self.not_found_message)
        return connection

    @staticmethod
    def _clean(value: str, field: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(char in cleaned for char in "\r\n\x00"):
            raise DomainValidationError(f"Invalid {field}")
        return cleaned

    async def _mark_changed(self, connection: DatabaseConnectionDB) -> None:
        connection.desired_revision += 1
        connection.status = DatabaseConnectionStatus.pending
        connection.last_error = None
        self.db.add(connection)
        server = await self.mcp_servers.get_scoped(connection.mcp_server_id)
        server.disabled_tools = sorted(
            set(server.disabled_tools) | allowed_tool_names(connection.id)
        )
        self.db.add(server)
        await self.db.flush()

    async def to_response(
        self, connection: DatabaseConnectionDB
    ) -> DatabaseConnectionResponse:
        server = await self.mcp_servers.get_scoped(connection.mcp_server_id)
        sqlite_file = (
            await self.files.get_scoped(connection.sqlite_file_id)
            if connection.sqlite_file_id
            else None
        )
        return DatabaseConnectionResponse(
            id=connection.id,
            mcp_server_id=connection.mcp_server_id,
            name=server.name,
            icon_url=server.icon_url or DATABASE_ENGINE_ICON_URLS[connection.engine],
            image_revision=server.image_revision,
            description=server.description,
            group=server.group,
            engine=connection.engine,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            sqlite_file_id=connection.sqlite_file_id,
            sqlite_file_name=sqlite_file.original_name if sqlite_file else None,
            sqlite_file_size_bytes=sqlite_file.size_bytes if sqlite_file else None,
            ssl_mode=connection.ssl_mode,
            connection_timeout=connection.connection_timeout,
            query_timeout=connection.query_timeout,
            readonly=connection.readonly,
            max_rows=connection.max_rows,
            visibility=server.visibility,
            team_ids=await self.mcp_servers.repository.list_team_ids(server.id),
            status=connection.status,
            last_error=_public_connection_error(connection.last_error),
            has_password=connection.engine is not DatabaseEngine.sqlite,
            desired_revision=connection.desired_revision,
            applied_revision=connection.applied_revision,
            last_applied_at=connection.last_applied_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    async def upload_sqlite_file(
        self, upload: UploadFile, user: UserDB
    ) -> SQLiteFileResponse:
        if not dbhub_settings.enabled or not dbhub_settings.auth_token:
            raise DomainValidationError("The internal database connector is disabled")
        stored = await store_sqlite_upload(upload)
        database_file = await self.files.create(
            DatabaseFileCreateDB(
                workspace_id=self.workspace_id,
                owner_id=user.id,
                original_name=stored.original_name,
                stored_name=stored.stored_name,
                size_bytes=stored.size_bytes,
            )
        )
        return SQLiteFileResponse(
            id=database_file.id,
            original_name=database_file.original_name,
            size_bytes=database_file.size_bytes,
        )

    async def list_responses(self) -> list[DatabaseConnectionResponse]:
        return [
            await self.to_response(connection)
            for connection in await self.repository.list_scoped()
        ]

    async def status(self) -> DatabaseConnectorStatusResponse:
        state = await self.repository.get_control_state()
        reachable = False
        source_count = 0
        if dbhub_settings.enabled and dbhub_settings.auth_token:
            try:
                source_count = len(await list_dbhub_source_ids())
                reachable = True
            except Exception:  # noqa: BLE001 — status reports unreachability
                reachable = False
        return DatabaseConnectorStatusResponse(
            enabled=dbhub_settings.enabled,
            reachable=reachable,
            desired_revision=state.desired_revision,
            applied_revision=state.applied_revision,
            source_count=max(0, source_count - 1),
            last_error=state.last_error,
            last_applied_at=state.last_applied_at,
        )

    async def create(
        self, data: DatabaseConnectionCreate, user: UserDB
    ) -> DatabaseConnectionResponse:
        if not dbhub_settings.enabled or not dbhub_settings.auth_token:
            raise DomainValidationError("The internal database connector is disabled")

        sqlite_file: DatabaseFileDB | None = None
        if data.engine is DatabaseEngine.sqlite:
            if data.sqlite_file_id is None:
                raise DomainValidationError("Upload a SQLite database file")
            sqlite_file = await self.files.get_scoped(data.sqlite_file_id)
            if sqlite_file is None:
                raise DomainValidationError("SQLite database file not found")
            host = None
            port = None
            database = sqlite_file.original_name
            username = None
            ssl_mode = None
        else:
            if (
                data.host is None
                or data.port is None
                or data.database is None
                or data.username is None
                or data.password is None
            ):
                raise DomainValidationError(
                    "Host, port, database, username, and password are required"
                )
            host = self._clean(data.host, "host")
            port = data.port
            database = self._clean(data.database, "database")
            username = self._clean(data.username, "username")
            ssl_mode = data.ssl_mode.strip() if data.ssl_mode else None

        await self.repository.bump_desired_revision()
        connection_id = uuid4()
        server = await self.mcp_servers.create(
            MCPServerCreate(
                name=self._clean(data.name, "name"),
                description=(data.description.strip() if data.description else None),
                url=dbhub_settings.mcp_url,
                auth_type=MCPAuthType.api_key,
                api_key=dbhub_settings.auth_token,
                visibility=data.visibility,
                team_ids=data.team_ids,
                group=data.group,
            ),
            user.id,
        )
        await self.mcp_servers.repository.mark_managed(
            server,
            managed_by=DBHUB_MANAGED_BY,
            resource_id=connection_id,
        )
        connection = DatabaseConnectionDB(
            id=connection_id,
            workspace_id=self.workspace_id,
            owner_id=user.id,
            mcp_server_id=server.id,
            source_id=source_id_for_connection(connection_id),
            engine=data.engine,
            host=host,
            port=port,
            database=database,
            username=username,
            sqlite_file_id=sqlite_file.id if sqlite_file else None,
            ssl_mode=ssl_mode,
            connection_timeout=data.connection_timeout,
            query_timeout=data.query_timeout,
            readonly=data.readonly,
            max_rows=data.max_rows,
        )
        self.db.add(connection)
        await self.db.flush()
        if data.password:
            await self.repository.set_password(connection.id, data.password)
        await self.db.refresh(connection)
        return await self.to_response(connection)

    async def update(
        self, connection_id: UUID, data: DatabaseConnectionPatch
    ) -> DatabaseConnectionResponse:
        connection = await self.get_scoped(connection_id, for_update=True)
        server_fields = {"name", "description", "group", "visibility"}
        server_update = data.model_dump(include=server_fields, exclude_unset=True)
        if "team_ids" in data.model_fields_set:
            server_update["team_ids"] = data.team_ids
        if "name" in server_update:
            if server_update["name"] is None:
                raise DomainValidationError("Invalid name")
            server_update["name"] = self._clean(server_update["name"], "name")
        if "visibility" in server_update and server_update["visibility"] is None:
            raise DomainValidationError("Invalid visibility")

        update_data = data.model_dump(
            exclude_unset=True,
            exclude={
                "name",
                "description",
                "group",
                "password",
                "visibility",
                "team_ids",
            },
        )
        required_fields = {
            "engine",
            "connection_timeout",
            "query_timeout",
            "readonly",
            "max_rows",
        }
        for field in required_fields & update_data.keys():
            if update_data[field] is None:
                raise DomainValidationError(f"Invalid {field}")
        target_engine = data.engine or connection.engine
        if target_engine is DatabaseEngine.sqlite:
            file_id = (
                data.sqlite_file_id
                if "sqlite_file_id" in data.model_fields_set
                else connection.sqlite_file_id
            )
            if file_id is None:
                raise DomainValidationError("Upload a SQLite database file")
            sqlite_file = await self.files.get_scoped(file_id)
            if sqlite_file is None:
                raise DomainValidationError("SQLite database file not found")
            if (
                connection.engine is not DatabaseEngine.sqlite
                or "sqlite_file_id" in data.model_fields_set
            ):
                update_data.update(
                    host=None,
                    port=None,
                    database=sqlite_file.original_name,
                    username=None,
                    sqlite_file_id=sqlite_file.id,
                    ssl_mode=None,
                )
        else:
            if connection.engine is DatabaseEngine.sqlite and not all(
                (data.host, data.port, data.database, data.username)
            ):
                raise DomainValidationError(
                    "Host, port, database, and username are required"
                )
            remote_values = {
                "host": update_data.get("host", connection.host),
                "port": update_data.get("port", connection.port),
                "database": update_data.get("database", connection.database),
                "username": update_data.get("username", connection.username),
            }
            if not all(remote_values.values()):
                raise DomainValidationError(
                    "Host, port, database, and username are required"
                )
            for field in ("host", "database", "username"):
                if field in update_data:
                    update_data[field] = self._clean(remote_values[field], field)
            if (
                connection.engine is DatabaseEngine.sqlite
                or "sqlite_file_id" in data.model_fields_set
            ):
                update_data["sqlite_file_id"] = None
            if update_data.get("ssl_mode"):
                update_data["ssl_mode"] = update_data["ssl_mode"].strip()
            has_password = await self.repository.get_password(connection.id)
            if not data.password and not has_password:
                raise DomainValidationError("Password is required")

        database_changed = bool(update_data) or "password" in data.model_fields_set
        if database_changed:
            await self.repository.bump_desired_revision()

        if server_update:
            await self.mcp_servers.update(
                connection.mcp_server_id,
                MCPServerPatch.model_validate(server_update),
                _managed_by=DBHUB_MANAGED_BY,
            )
        for key, value in update_data.items():
            setattr(connection, key, value)
        if target_engine is DatabaseEngine.sqlite:
            await self.repository.delete_password(connection.id)
        elif data.password:
            await self.repository.set_password(connection.id, data.password)
        if database_changed:
            await self._mark_changed(connection)
        await self.db.refresh(connection)
        return await self.to_response(connection)

    async def request_reconcile(self, connection_id: UUID) -> None:
        await self.repository.bump_desired_revision()
        connection = await self.get_scoped(connection_id, for_update=True)
        await self._mark_changed(connection)

    async def delete(self, connection_id: UUID, *, detach_agents: bool = False) -> UUID:
        await self.repository.bump_desired_revision()
        connection = await self.get_scoped(connection_id, for_update=True)
        server_id = connection.mcp_server_id
        if detach_agents:
            await AgentMCPServerService(self.db, self.workspace_id).detach_server(
                server_id
            )
        await self.repository.delete(connection)
        await self.mcp_servers.delete(server_id, _managed_by=DBHUB_MANAGED_BY)
        return server_id


def get_database_connection_service(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_active_workspace_id),
) -> DatabaseConnectionService:
    return DatabaseConnectionService(db, workspace_id)
