import asyncio
from collections.abc import Collection
from typing import Any

import httpx2

from app.database_connections.settings import dbhub_settings
from app.mcp.client.connection import ConnectionSpec, open_client


def _sources(payload: Any) -> dict[str, str | None]:
    if isinstance(payload, list):
        return {
            item["id"]: (
                item.get("description")
                if isinstance(item.get("description"), str)
                else None
            )
            for item in payload
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
    if isinstance(payload, dict):
        for key in ("sources", "data"):
            if key in payload:
                return _sources(payload[key])
    return {}


async def list_dbhub_sources() -> dict[str, str | None]:
    headers = {"Authorization": f"Bearer {dbhub_settings.auth_token}"}
    async with httpx2.AsyncClient(headers=headers, timeout=10.0) as client:
        response = await client.get(f"{dbhub_settings.url.rstrip('/')}/api/sources")
        response.raise_for_status()
        return _sources(response.json())


async def list_dbhub_source_ids() -> set[str]:
    return set(await list_dbhub_sources())


async def inspect_dbhub_tools(
    source_ids: Collection[str],
    *,
    execute_check_source_ids: Collection[str] = (),
) -> tuple[set[str], set[str]]:
    spec = ConnectionSpec(
        url=dbhub_settings.mcp_url,
        headers={"Authorization": f"Bearer {dbhub_settings.auth_token}"},
    )
    async with open_client(spec) as client:
        tool_names = {tool.name for tool in await client.list_tools()}
        execute_check_ids = set(execute_check_source_ids)
        checks = []
        for source_id in source_ids:
            if source_id in execute_check_ids:
                tool_name = f"execute_sql_{source_id}"
                arguments = {"sql": "SELECT 1"}
            else:
                tool_name = f"health_check_{source_id}"
                arguments = {}
            if tool_name in tool_names:
                checks.append((source_id, client.call_tool(tool_name, arguments)))
        results = await asyncio.gather(
            *(check for _, check in checks),
            return_exceptions=True,
        )
        healthy_sources = {
            source_id
            for (source_id, _), result in zip(checks, results, strict=True)
            if not isinstance(result, BaseException)
        }
        return tool_names, healthy_sources
