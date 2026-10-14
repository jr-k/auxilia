from uuid import UUID

from app.exceptions import DomainValidationError


DBHUB_MANAGED_BY = "dbhub"
DBHUB_TOOL_BASES = (
    "execute_sql",
    "search_objects",
    "explain_sql",
    "health_check",
)
DBHUB_WRITE_SOURCE_SUFFIX = "_write"


def source_id_for_connection(connection_id: UUID) -> str:
    return f"db_{connection_id.hex}"


def write_source_id_for_connection(connection_id: UUID) -> str:
    return f"{source_id_for_connection(connection_id)}{DBHUB_WRITE_SOURCE_SUFFIX}"


def read_sql_tool_name(connection_id: UUID) -> str:
    return f"execute_sql_{source_id_for_connection(connection_id)}"


def write_sql_tool_name(connection_id: UUID) -> str:
    return f"execute_sql_{write_source_id_for_connection(connection_id)}"


def configured_source_ids(
    connection_id: UUID, *, writes_enabled: bool
) -> tuple[str, ...]:
    source_id = source_id_for_connection(connection_id)
    if not writes_enabled:
        return (source_id,)
    return (source_id, write_source_id_for_connection(connection_id))


def configured_tool_names(
    connection_id: UUID,
    *,
    writes_enabled: bool,
    sqlite: bool,
) -> set[str]:
    source_id = source_id_for_connection(connection_id)
    names = {
        f"{name}_{source_id}"
        for name in DBHUB_TOOL_BASES
        if not (sqlite and name == "health_check")
    }
    if writes_enabled:
        names.add(write_sql_tool_name(connection_id))
    return names


def allowed_tool_names(connection_id: UUID) -> set[str]:
    # The live DBHub list remains authoritative: read-only connections do not
    # configure the write source, so its tool cannot be returned or called.
    # Keeping the full potential set here lets a write-enabled connection expose
    # both SQL tools without another database read at every MCP filtering seam.
    return configured_tool_names(
        connection_id,
        writes_enabled=True,
        sqlite=False,
    )


def filter_managed_tools(server, tools):
    if server.managed_by != DBHUB_MANAGED_BY:
        return tools
    if server.managed_resource_id is None:
        return []
    allowed = allowed_tool_names(server.managed_resource_id)
    disabled = set(server.disabled_tools)
    return [
        tool for tool in tools if tool.name in allowed and tool.name not in disabled
    ]


def ensure_managed_tool_allowed(server, tool_name: str) -> None:
    if server.managed_by != DBHUB_MANAGED_BY:
        return
    if server.managed_resource_id is None:
        raise DomainValidationError("Database connection metadata is incomplete")
    if tool_name not in allowed_tool_names(server.managed_resource_id):
        raise DomainValidationError(
            "Tool is not available for this database connection"
        )
    if tool_name in server.disabled_tools:
        raise DomainValidationError("Database connection is not ready")
