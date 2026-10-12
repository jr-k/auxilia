from collections.abc import Iterable

import tomli_w

from app.database_connections.models import DatabaseConnectionDB
from app.database_connections.tools import DBHUB_TOOL_BASES


BOOTSTRAP_SOURCE_ID = "_auxilia_bootstrap"


def source_description(connection: DatabaseConnectionDB) -> str:
    return (
        f"Auxilia managed source {connection.id}; "
        f"revision {connection.desired_revision}"
    )


def build_dbhub_config(
    connections: Iterable[tuple[DatabaseConnectionDB, str]],
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

    for connection, password in connections:
        source: dict[str, object] = {
            "id": connection.source_id,
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
        sources.append(source)

        for tool_name in DBHUB_TOOL_BASES:
            tool: dict[str, object] = {
                "name": tool_name,
                "source": connection.source_id,
            }
            if tool_name == "execute_sql":
                tool["readonly"] = connection.readonly
                tool["max_rows"] = connection.max_rows
            tools.append(tool)

    return tomli_w.dumps({"sources": sources, "tools": tools})
