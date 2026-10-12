import asyncio
import logging
import os
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
from app.database_connections.models import DatabaseConnectionStatus
from app.database_connections.repository import DatabaseConnectionRepository
from app.database_connections.settings import dbhub_settings
from app.database_connections.tools import allowed_tool_names
from app.mcp.servers.repository import MCPServerRepository


logger = logging.getLogger(__name__)
_LOCK_ID = 0x4442485542  # "DBHUB"


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


class DBHubReconciler:
    def __init__(self) -> None:
        self._loop = PeriodicLoop(
            "dbhub-reconciler",
            dbhub_settings.reconcile_interval_seconds,
            self._tick,
        )

    async def ensure_config_file(self) -> None:
        if not dbhub_settings.enabled:
            return
        content = await self._render()
        await asyncio.to_thread(_write_in_place, dbhub_settings.config_path, content)

    async def _render(self) -> str:
        async with AsyncSessionLocal() as db:
            repository = DatabaseConnectionRepository(db)
            connections = await repository.list_all()
            hydrated = [
                (connection, await repository.get_password(connection.id))
                for connection in connections
            ]
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
                hydrated = [
                    (connection, await repository.get_password(connection.id))
                    for connection in connections
                ]
                content = build_dbhub_config(hydrated)

                await asyncio.to_thread(
                    _write_in_place, dbhub_settings.config_path, content
                )
                # DBHub debounces filesystem changes for 500 ms.
                await asyncio.sleep(0.75)
                sources, tool_state = await asyncio.gather(
                    list_dbhub_sources(),
                    inspect_dbhub_tools(
                        [connection.source_id for connection in connections]
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
                            "DBHub could not connect to this source"
                            if applied
                            else "DBHub did not apply this source"
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
                    state.last_error = "One or more DBHub sources failed to apply"
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
