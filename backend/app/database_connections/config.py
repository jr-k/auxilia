from collections.abc import Iterable

import tomli_w

from app.database_connections.models import DatabaseConnectionDB, DatabaseEngine
from app.database_connections.settings import database_file_settings
from app.database_connections.tools import (
    DBHUB_TOOL_BASES,
    configured_source_ids,
)


BOOTSTRAP_SOURCE_ID = "_auxilia_bootstrap"
GENERATED_CONFIG_HEADER = "# auxilia-generated-config-version = 2\n"


def source_description(connection: DatabaseConnectionDB) -> str:
    return (
        f"Auxilia managed source {connection.id}; "
        f"revision {connection.desired_revision}"
    )


def _source_config(
    connection: DatabaseConnectionDB,
    password: str | None,
    sqlite_stored_name: str | None,
    source_id: str,
) -> dict[str, object]:
    if connection.engine is DatabaseEngine.sqlite:
        if sqlite_stored_name is None:
            raise ValueError(f"Missing SQLite file for {connection.id}")
        sqlite_path = database_file_settings.runtime_path / sqlite_stored_name
        return {
            "id": source_id,
            "description": source_description(connection),
            "dsn": f"sqlite://{sqlite_path}",
            "lazy": True,
            "query_timeout": connection.query_timeout,
        }

    if password is None:
        raise ValueError(f"Missing database password for {connection.id}")
    source: dict[str, object] = {
        "id": source_id,
        "description": source_description(connection),
        "type": connection.engine.value,
        "host": connection.host,
        "port": connection.port,
        "database": connection.database,
        "user": connection.username,
        "password": password,
        "lazy": True,
        "connection_timeout": connection.connection_timeout,
        "query_timeout": connection.query_timeout,
    }
    if connection.ssl_mode:
        source["sslmode"] = connection.ssl_mode
    return source


def build_dbhub_config(
    connections: Iterable[tuple[DatabaseConnectionDB, str | None, str | None]],
) -> str:
    sources: list[dict[str, object]] = [
        {
            "id": BOOTSTRAP_SOURCE_ID,
            "description": "Auxilia control-plane bootstrap source",
            "dsn": "sqlite:///:memory:",
            "lazy": True,
        }
    ]
    tools: list[dict[str, object]] = [
        {
            "name": "search_objects",
            "source": BOOTSTRAP_SOURCE_ID,
        }
    ]

    for connection, password, sqlite_stored_name in connections:
        writes_enabled = not connection.readonly
        source_ids = configured_source_ids(
            connection.id,
            writes_enabled=writes_enabled,
        )
        sources.extend(
            _source_config(
                connection,
                password,
                sqlite_stored_name,
                source_id,
            )
            for source_id in source_ids
        )

        for tool_name in DBHUB_TOOL_BASES:
            if (
                connection.engine is DatabaseEngine.sqlite
                and tool_name == "health_check"
            ):
                continue
            tool: dict[str, object] = {
                "name": tool_name,
                "source": connection.source_id,
            }
            if tool_name == "execute_sql":
                # Reads stay independently configurable on every agent. Writes
                # use a second DBHub source below, so enabling them never turns
                # this tool into an unrestricted SQL endpoint.
                tool["readonly"] = True
                tool["max_rows"] = connection.max_rows
            tools.append(tool)

        if writes_enabled:
            tools.append(
                {
                    "name": "execute_sql",
                    "source": source_ids[1],
                    "readonly": False,
                    "max_rows": connection.max_rows,
                }
            )
            if connection.engine is not DatabaseEngine.sqlite:
                # The reconciler probes remote write sources through DBHub's
                # engine-aware health check (portable to Oracle and SQL Server).
                # Managed-tool filtering keeps this internal duplicate hidden.
                tools.append(
                    {
                        "name": "health_check",
                        "source": source_ids[1],
                    }
                )

    return GENERATED_CONFIG_HEADER + tomli_w.dumps({"sources": sources, "tools": tools})
