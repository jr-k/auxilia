import asyncio
import logging
import os
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from app.agents.mcp_servers.repository import AgentMCPServerRepository
from app.agents.mcp_servers.service import AgentMCPServerService
from app.background import PeriodicLoop
from app.database import AsyncSessionLocal
from app.database_connections.client import (
    inspect_dbhub_tools,
    list_dbhub_sources,
)
from app.database_connections.config import (
    BOOTSTRAP_SOURCE_ID,
    build_dbhub_config,
    source_description,
)
from app.database_connections.files import delete_untracked_files
from app.database_connections.models import (
    DatabaseConnectionDB,
    DatabaseConnectionStatus,
    DatabaseEngine,
)
from app.database_connections.repository import (
    DatabaseConnectionRepository,
    DatabaseFileRepository,
)
from app.database_connections.settings import dbhub_settings
from app.database_connections.tools import allowed_tool_names
from app.mcp.servers.repository import MCPServerRepository


logger = logging.getLogger(__name__)
_LOCK_ID = 0x4442485542  # "DBHUB"
_FILE_CLEANUP_INTERVAL_SECONDS = 300


def _write_in_place(path: Path, content: str) -> None:
    tomllib.loads(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "r+" if path.exists() else "w"
    with path.open(mode, encoding="utf-8") as handle:
        handle.seek(0)
        handle.write(content)
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600)


async def _hydrate_connections(
    repository: DatabaseConnectionRepository,
    connections: list[DatabaseConnectionDB],
) -> list[tuple[DatabaseConnectionDB, str | None, str | None]]:
    hydrated: list[tuple[DatabaseConnectionDB, str | None, str | None]] = []
    for connection in connections:
        stored_name = None
        if connection.sqlite_file_id is not None:
            database_file = await DatabaseFileRepository(
                repository.db, connection.workspace_id
            ).get_scoped(connection.sqlite_file_id)
            stored_name = database_file.stored_name if database_file else None
        hydrated.append(
            (
                connection,
                await repository.get_password(connection.id),
                stored_name,
            )
        )
    return hydrated


class DBHubReconciler:
    def __init__(self) -> None:
        self._last_file_cleanup = 0.0
        self._loop = PeriodicLoop(
            "dbhub-reconciler",
            dbhub_settings.reconcile_interval_seconds,
            self._tick,
        )

    async def ensure_config_file(self) -> None:
        if not dbhub_settings.enabled:
            return
        await self._cleanup_orphaned_files(force=True)
        content = await self._render()
        await asyncio.to_thread(_write_in_place, dbhub_settings.config_path, content)

    async def _cleanup_orphaned_files(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and now - self._last_file_cleanup < _FILE_CLEANUP_INTERVAL_SECONDS
        ):
            return
        self._last_file_cleanup = now
        try:
            async with AsyncSessionLocal() as db:
                known_names = await DatabaseFileRepository(db).list_stored_names()
            deleted = await delete_untracked_files(known_names)
            if deleted:
                logger.info("Removed %s orphaned database file(s)", deleted)
        except Exception:
            logger.exception("Could not clean orphaned database files")

    async def _render(self) -> str:
        async with AsyncSessionLocal() as db:
            repository = DatabaseConnectionRepository(db)
            connections = await repository.list_all()
            hydrated = await _hydrate_connections(repository, connections)
            return build_dbhub_config(hydrated)

    async def _set_failure(self, error_type: str) -> None:
        async with AsyncSessionLocal() as db, db.begin():
            repository = DatabaseConnectionRepository(db)
            state = await repository.get_control_state(for_update=True)
            state.last_error = error_type
            db.add(state)

    async def _tick(self) -> None:
        if not dbhub_settings.enabled:
            return
        if not dbhub_settings.auth_token:
            await self._set_failure("MissingDBHubAuthToken")
            return
        await self._cleanup_orphaned_files()

        try:
            async with AsyncSessionLocal() as db, db.begin():
                # Keep this transaction open through config verification. The
                # transaction-scoped advisory lock would otherwise be released
                # before the file write, allowing two replicas to race.
                locked = (
                    await db.execute(
                        text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                        {"lock_id": _LOCK_ID},
                    )
                ).scalar_one()
                if not locked:
                    return
                repository = DatabaseConnectionRepository(db)
                state = await repository.get_control_state(for_update=True)
                connections = await repository.list_all()
                mcp_repository = MCPServerRepository(db)
                for connection in connections:
                    server = await mcp_repository.get_scoped(connection.mcp_server_id)
                    if (
                        server is not None
                        and await mcp_repository.get_api_key(server.id)
                        != dbhub_settings.auth_token
                    ):
                        await mcp_repository.create_or_update_api_key(
                            server.id, dbhub_settings.auth_token
                        )
                if (
                    state.desired_revision == state.applied_revision
                    and dbhub_settings.config_path.exists()
                ):
                    return
                desired_revision = state.desired_revision
                hydrated = await _hydrate_connections(repository, connections)
                content = build_dbhub_config(hydrated)

                await asyncio.to_thread(
                    _write_in_place, dbhub_settings.config_path, content
                )
                # DBHub debounces filesystem changes for 500 ms.
                await asyncio.sleep(0.75)
                sources, tool_state = await asyncio.gather(
                    list_dbhub_sources(),
                    inspect_dbhub_tools(
                        [connection.source_id for connection in connections],
                        sqlite_source_ids=[
                            connection.source_id
                            for connection in connections
                            if connection.engine is DatabaseEngine.sqlite
                        ],
                    ),
                )
                tool_names, healthy_sources = tool_state

                expected_sources = {
                    BOOTSTRAP_SOURCE_ID,
                    *(connection.source_id for connection in connections),
                }
                now = datetime.now(UTC)
                all_ready = set(sources) == expected_sources

                binding_repository = AgentMCPServerRepository(db)
                current_connections = await repository.list_all()
                for connection in current_connections:
                    allowed = allowed_tool_names(connection.id)
                    if connection.engine is DatabaseEngine.sqlite:
                        allowed.discard(f"health_check_{connection.source_id}")
                    applied = sources.get(connection.source_id) == source_description(
                        connection
                    ) and allowed.issubset(tool_names)
                    ready = applied and connection.source_id in healthy_sources
                    connection.status = (
                        DatabaseConnectionStatus.ready
                        if ready
                        else DatabaseConnectionStatus.error
                    )
                    connection.last_error = (
                        None
                        if ready
                        else (
                            "Could not connect to the database"
                            if applied
                            else "The database connection could not be configured"
                        )
                    )
                    if ready:
                        connection.applied_revision = connection.desired_revision
                        connection.last_applied_at = now
                    else:
                        all_ready = False
                    db.add(connection)

                    server = await mcp_repository.get_scoped(connection.mcp_server_id)
                    if server is not None:
                        server.disabled_tools = [] if ready else sorted(allowed)
                        db.add(server)
                        if ready:
                            agent_service = AgentMCPServerService(
                                db, connection.workspace_id
                            )
                            for binding in await binding_repository.list_for_server(
                                server.id
                            ):
                                await agent_service.sync_binding(
                                    binding, server, str(connection.owner_id)
                                )

                state = await repository.get_control_state(for_update=True)
                if all_ready:
                    state.applied_revision = desired_revision
                    state.last_error = None
                    state.last_applied_at = now
                else:
                    state.last_error = (
                        "One or more database connections could not be configured"
                    )
                db.add(state)
        except Exception as exc:
            await self._set_failure(type(exc).__name__)
            raise

        if all_ready:
            last_good = dbhub_settings.config_path.with_suffix(".last-good.toml")
            await asyncio.to_thread(_write_in_place, last_good, content)

    async def run(self) -> None:
        await self._loop.run()

    def stop(self) -> None:
        self._loop.stop()
