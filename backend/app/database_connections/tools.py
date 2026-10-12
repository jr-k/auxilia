from uuid import UUID

from app.exceptions import DomainValidationError


DBHUB_MANAGED_BY = "dbhub"
DBHUB_TOOL_BASES = (
    "execute_sql",
    "search_objects",
    "explain_sql",
    "health_check",
)


def source_id_for_connection(connection_id: UUID) -> str:
    return f"db_{connection_id.hex}"


def allowed_tool_names(connection_id: UUID) -> set[str]:
    source_id = source_id_for_connection(connection_id)
    return {f"{name}_{source_id}" for name in DBHUB_TOOL_BASES}


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
