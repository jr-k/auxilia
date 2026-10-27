"""Model-driven MCP tool discovery: per-prompt server routing and search."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated, Any, cast

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.human_in_the_loop import InterruptOnConfig
from langchain.agents.middleware.internal_call_transformer import (
    InternalCallTransformer,
    internal_call_metadata,
)
from langchain.agents.middleware.types import (
    AgentState,
    ModelRequest,
    ModelResponse,
    PrivateStateAttr,
    ToolCallRequest,
)
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command, Overwrite

from app.agents.models import ToolDiscoveryMode
from app.runtime.tool_catalog import SearchHit, ToolCatalog, tool_server_name


logger = logging.getLogger(__name__)

LOCAL_DISCOVERY_STATE_KEY = "selected_mcp_tools"
LOCAL_DISCOVERY_CANDIDATES_KEY = "mcp_tool_candidates"
LOCAL_PREFETCH_LIMIT = 4
LOCAL_VISIBLE_LIMIT = 6
LOCAL_RESULT_LIMIT = 6
LOCAL_ROUTER_SERVER_LIMIT = 3
LOCAL_ROUTER_CATALOG_LIMIT = 48
LAZY_DESCRIPTION_LIMIT = 140
LAZY_QUERY_LIMIT = 4000

LAZY_ROUTER_PROMPT = (
    "You route one user request to MCP servers. Return the names of the MCP "
    "servers whose tools this request needs, nothing else. Return an empty "
    "list when the request needs no MCP tool. Keep a server that was active "
    "in the previous turn when the request continues work with it."
)


def _merge_tool_names(left: list[str], right: list[str] | Overwrite) -> list[str]:
    if isinstance(right, Overwrite):
        return list(right.value)
    merged = list(left)
    for name in right:
        if name in merged:
            merged.remove(name)
        merged.append(name)
    return merged[-LOCAL_VISIBLE_LIMIT:]


def _merge_candidate_names(_left: list[str], right: list[str] | Overwrite) -> list[str]:
    if isinstance(right, Overwrite):
        return list(right.value)
    return list(dict.fromkeys(right))[-(LOCAL_RESULT_LIMIT * 3) :]


class LocalToolDiscoveryState(AgentState[Any], total=False):
    selected_mcp_tools: Annotated[
        list[str],
        PrivateStateAttr,
        _merge_tool_names,
    ]
    mcp_tool_candidates: Annotated[
        list[str],
        PrivateStateAttr,
        _merge_candidate_names,
    ]


def _selected_tool_names(state: Mapping[str, Any]) -> frozenset[str]:
    raw = state.get(LOCAL_DISCOVERY_STATE_KEY, [])
    if isinstance(raw, Overwrite):
        raw = raw.value
    return frozenset(cast(list[str], raw))


def _candidate_tool_names(state: Mapping[str, Any]) -> frozenset[str]:
    raw = state.get(LOCAL_DISCOVERY_CANDIDATES_KEY, [])
    if isinstance(raw, Overwrite):
        raw = raw.value
    return frozenset(cast(list[str], raw))


def _last_human_text(state: Mapping[str, Any]) -> str:
    messages = state.get("messages", [])
    for message in reversed(messages if isinstance(messages, list) else []):
        if isinstance(message, HumanMessage):
            text = str(message.text)
            start_marker = "<current_request>\n"
            end_marker = "\n</current_request>"
            start = text.rfind(start_marker)
            end = text.rfind(end_marker)
            if start >= 0 and end > start:
                return text[start + len(start_marker) : end].strip()
            return text
    return ""


def _free_tool_name(base: str, reserved: set[str]) -> str:
    name = base
    suffix = 2
    while name in reserved:
        name = f"{base}_{suffix}"
        suffix += 1
    return name


class HiddenSchemaMiddleware(AgentMiddleware[LocalToolDiscoveryState]):
    """Expose only the MCP tools listed in ``selected_mcp_tools``.

    The model request drops every other MCP schema, and a call to a hidden
    tool returns an error ToolMessage instead of executing. Subclasses decide
    how the selection is filled and what the error tells the model to do.
    """

    state_schema = LocalToolDiscoveryState
    transformers = (InternalCallTransformer,)

    def __init__(self, searchable_tools: list[BaseTool]) -> None:
        self.searchable_tools = list(searchable_tools)
        self.searchable_tool_names = frozenset(
            tool.name for tool in self.searchable_tools
        )

    def _hidden_tool_hint(self, name: str) -> str:
        raise NotImplementedError

    def _filter_request(self, request: ModelRequest) -> ModelRequest:
        selected = _selected_tool_names(request.state)
        visible = [
            tool
            for tool in request.tools
            if not (
                isinstance(tool, BaseTool)
                and tool.name in self.searchable_tool_names
                and tool.name not in selected
            )
        ]
        return request.override(tools=visible)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | AIMessage:
        return handler(self._filter_request(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse | AIMessage:
        return await handler(self._filter_request(request))

    def _hidden_tool_error(self, request: ToolCallRequest) -> ToolMessage | None:
        name = request.tool_call["name"]
        selected = _selected_tool_names(request.state)
        if name not in self.searchable_tool_names or name in selected:
            return None
        return ToolMessage(
            content=self._hidden_tool_hint(name),
            tool_call_id=request.tool_call["id"],
            name=name,
            status="error",
        )

    def wrap_tool_call(self, request: ToolCallRequest, handler):
        if error := self._hidden_tool_error(request):
            return error
        return handler(request)

    async def awrap_tool_call(self, request: ToolCallRequest, handler):
        if error := self._hidden_tool_error(request):
            return error
        return await handler(request)


class LazyToolDiscoveryMiddleware(HiddenSchemaMiddleware):
    """Cherry-pick MCP servers per prompt with one minimal-effort model call.

    Before each turn the router sees only the server names (plus a one-line
    description when the admin wrote one) and answers which servers the
    request needs; every tool of those servers becomes visible, nothing else
    is loaded. A small ``activate_mcp_servers`` tool lets the model widen the
    selection mid-turn when the router missed a server.
    """

    def __init__(
        self,
        searchable_tools: list[BaseTool],
        *,
        model,
        server_descriptions: Mapping[str, str | None] | None = None,
    ) -> None:
        super().__init__(searchable_tools)
        self.model = model
        self.ordered_tool_names = [tool.name for tool in self.searchable_tools]
        tools_by_server: dict[str, list[str]] = {}
        for tool in self.searchable_tools:
            tools_by_server.setdefault(tool_server_name(tool), []).append(tool.name)
        self.tools_by_server = {
            server: tuple(names) for server, names in tools_by_server.items()
        }
        self.server_by_tool = {
            name: server
            for server, names in self.tools_by_server.items()
            for name in names
        }
        self.server_descriptions = dict(server_descriptions or {})
        self.activate_tool_name = _free_tool_name(
            "activate_mcp_servers", set(self.searchable_tool_names)
        )
        self.tools = [
            StructuredTool.from_function(
                func=self._activate,
                name=self.activate_tool_name,
                description=(
                    "Activate MCP servers whose tools are not visible yet. Pass "
                    "exact server names; their tools become available on the "
                    "next step. Available servers: " + ", ".join(self.tools_by_server)
                ),
            ),
        ]

    def _server_lines(self) -> str:
        lines = []
        for server in self.tools_by_server:
            description = self.server_descriptions.get(server)
            compact = " ".join(description.split()) if description else ""
            if compact:
                lines.append(f"- {server}: {compact[:LAZY_DESCRIPTION_LIMIT]}")
            else:
                lines.append(f"- {server}")
        return "\n".join(lines)

    def _active_servers(self, state: Mapping[str, Any]) -> list[str]:
        return list(
            dict.fromkeys(
                self.server_by_tool[name]
                for name in self.ordered_tool_names
                if name in _selected_tool_names(state) and name in self.server_by_tool
            )
        )

    def _tools_for(self, servers: list[str]) -> list[str]:
        wanted = set(servers)
        return [
            name
            for name in self.ordered_tool_names
            if self.server_by_tool.get(name) in wanted
        ]

    async def _route(self, query: str, previous: list[str]) -> list[str] | None:
        """The servers the request needs; ``None`` when the router failed."""
        server_names = list(self.tools_by_server)
        schema = {
            "title": "select_mcp_servers",
            "type": "object",
            "properties": {
                "servers": {
                    "type": "array",
                    "items": {"type": "string", "enum": server_names},
                }
            },
            "required": ["servers"],
            "additionalProperties": False,
        }
        prompt = f"{LAZY_ROUTER_PROMPT}\n\nMCP servers:\n{self._server_lines()}"
        if previous:
            prompt += "\n\nActive in the previous turn: " + ", ".join(previous)
        try:
            routed = await self.model.with_structured_output(schema).ainvoke(
                [SystemMessage(prompt), HumanMessage(query[:LAZY_QUERY_LIMIT])],
                config={
                    "metadata": {
                        "lc_source": "auxilia_lazy_mcp_router",
                        **internal_call_metadata(),
                    }
                },
            )
        except Exception:  # noqa: BLE001 — routing degrades to every schema
            logger.warning("Lazy MCP router failed", exc_info=True)
            return None
        if not isinstance(routed, dict):
            return None
        raw = routed.get("servers", [])
        if not isinstance(raw, list):
            return None
        return list(
            dict.fromkeys(
                server
                for server in raw
                if isinstance(server, str) and server in self.tools_by_server
            )
        )

    async def abefore_agent(
        self, state: LocalToolDiscoveryState, runtime
    ) -> dict[str, Any]:
        query = _last_human_text(state)
        if not query:
            return {}
        previous = self._active_servers(state)
        servers = await self._route(query, previous)
        if servers is None:
            selected = list(self.ordered_tool_names)
            route = "fail_open"
        else:
            selected = self._tools_for(servers)
            route = "router"
        logger.info(
            "Lazy MCP discovery route=%s servers=%d tools=%d",
            route,
            len(servers or ()),
            len(selected),
        )
        return {
            LOCAL_DISCOVERY_STATE_KEY: Overwrite(selected),
            LOCAL_DISCOVERY_CANDIDATES_KEY: Overwrite([]),
        }

    def _activate(self, servers: list[str], runtime: ToolRuntime) -> Command:
        by_fold = {server.casefold(): server for server in self.tools_by_server}
        resolved = [
            by_fold[server.strip().casefold()]
            for server in servers
            if isinstance(server, str) and server.strip().casefold() in by_fold
        ]
        unknown = [
            server
            for server in servers
            if not isinstance(server, str) or server.strip().casefold() not in by_fold
        ]
        active = self._active_servers(runtime.state)
        merged = list(dict.fromkeys([*active, *resolved]))
        if resolved:
            content = (
                "Activated MCP servers: "
                + ", ".join(resolved)
                + ". Their tools are available on the next step."
            )
        else:
            content = "No MCP server activated."
        if unknown:
            content += (
                " Unknown servers ignored: "
                + ", ".join(str(server) for server in unknown)
                + ". Available: "
                + ", ".join(self.tools_by_server)
                + "."
            )
        logger.info(
            "Lazy MCP discovery activation requested=%d activated=%d",
            len(servers),
            len(resolved),
        )
        return Command(
            update={
                LOCAL_DISCOVERY_STATE_KEY: Overwrite(self._tools_for(merged)),
                "messages": [
                    ToolMessage(
                        content=content,
                        tool_call_id=runtime.tool_call_id or "",
                        name=self.activate_tool_name,
                        status="success" if resolved else "error",
                    )
                ],
            }
        )

    def _hidden_tool_hint(self, name: str) -> str:
        server = self.server_by_tool.get(name, "unknown")
        return (
            f"Tool '{name}' belongs to MCP server '{server}', which is not active "
            f"for this request. Call {self.activate_tool_name} with that server, "
            "then invoke the tool on the next step."
        )


class LocalToolDiscoveryMiddleware(HiddenSchemaMiddleware):
    """Prefetch a tiny MCP schema set, with compact adaptive widening."""

    def __init__(
        self,
        searchable_tools: list[BaseTool],
        *,
        model,
        catalog: ToolCatalog | None = None,
        server_context: str | None = None,
    ) -> None:
        super().__init__(searchable_tools)
        self.model = model
        self.server_context = server_context
        self.catalog = catalog or ToolCatalog(self.searchable_tools)
        self.searchable_tool_names = self.catalog.names
        search_name = _free_tool_name(
            "search_mcp_tools", set(self.searchable_tool_names)
        )
        load_name = _free_tool_name(
            "load_mcp_tools", {*self.searchable_tool_names, search_name}
        )
        self.search_tool_name = search_name
        self.load_tool_name = load_name
        self.tools = [
            StructuredTool.from_function(
                func=self._search,
                name=search_name,
                description=(
                    "Search the enabled MCP catalog when the visible tools do not "
                    "cover the request. Returns a short ranked list; high-confidence "
                    "matches are loaded automatically for the next model step. Use "
                    f"{load_name} to load another returned candidate. Use server and "
                    "offset to browse later pages when a precise search finds nothing."
                ),
            ),
            StructuredTool.from_function(
                func=self._load,
                name=load_name,
                description=(
                    "Load exact MCP tool names returned by the latest catalog search. "
                    "Load only the smallest set needed; at most six MCP schemas can "
                    "be visible at once."
                ),
            ),
        ]

    @staticmethod
    def _prefetch_hits(hits: tuple[SearchHit, ...]) -> tuple[SearchHit, ...]:
        if not hits:
            return ()
        floor = hits[0].score * 0.35
        plausible = tuple(
            hit for hit in hits if hit.score >= floor and hit.coverage >= 0.25
        )
        return ToolCatalog.diversify(plausible, LOCAL_PREFETCH_LIMIT)

    async def abefore_agent(
        self, state: LocalToolDiscoveryState, runtime
    ) -> dict[str, Any]:
        query = _last_human_text(state)
        lexical = self.catalog.search(query, limit=LOCAL_RESULT_LIMIT * 3)
        candidates = [hit.document.name for hit in lexical.hits]
        selected: list[str] = []
        route = "none"
        if lexical.confident:
            selected = [hit.document.name for hit in self._prefetch_hits(lexical.hits)]
            route = "lexical"
        elif query:
            selected = await self._route_with_model(query, lexical.hits)
            route = "router" if selected else "manual_widen"
        logger.info(
            "Precision discovery prefetch route=%s candidates=%d selected=%d margin=%.3f",
            route,
            len(candidates),
            len(selected),
            lexical.margin,
        )
        return {
            LOCAL_DISCOVERY_STATE_KEY: Overwrite(selected),
            LOCAL_DISCOVERY_CANDIDATES_KEY: Overwrite(candidates),
        }

    async def _route_with_model(
        self, query: str, lexical_hits: tuple[SearchHit, ...]
    ) -> list[str]:
        server_names = list(self.catalog.by_server)
        if not server_names:
            return []
        server_schema = {
            "title": "select_mcp_servers",
            "type": "object",
            "properties": {
                "servers": {
                    "type": "array",
                    "items": {"type": "string", "enum": server_names},
                    "maxItems": LOCAL_ROUTER_SERVER_LIMIT,
                },
                "intents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": LOCAL_PREFETCH_LIMIT,
                },
            },
            "required": ["servers", "intents"],
            "additionalProperties": False,
        }
        server_prompt = (
            "Select at most three MCP servers that can satisfy the request and "
            "rewrite its distinct intents as short capability phrases. Return no "
            "server when none is relevant.\n\nAvailable servers:\n"
            f"{self.server_context or self.catalog.server_index()}"
        )
        try:
            routed = await self.model.with_structured_output(server_schema).ainvoke(
                [
                    SystemMessage(server_prompt),
                    HumanMessage(query[:2000]),
                ],
                config={
                    "metadata": {
                        "lc_source": "auxilia_tool_server_router",
                        **internal_call_metadata(),
                    }
                },
            )
            if not isinstance(routed, dict):
                return []
            servers = [
                server
                for server in routed.get("servers", [])
                if isinstance(server, str) and server in self.catalog.by_server
            ][:LOCAL_ROUTER_SERVER_LIMIT]
            intents = [
                intent[:200]
                for intent in routed.get("intents", [])
                if isinstance(intent, str) and intent.strip()
            ][:LOCAL_PREFETCH_LIMIT]
            if not servers:
                return []
            lexical_names = [hit.document.name for hit in lexical_hits]
            server_set = set(servers)
            routed_names = [
                hit.document.name
                for intent in (intents or [query])
                for hit in self.catalog.search(
                    intent,
                    limit=LOCAL_RESULT_LIMIT * 2,
                    servers=server_set,
                ).hits
            ]
            # Round-robin fallback keeps every selected server represented even
            # when the rewritten intents find no lexical overlap.
            fallback_names: list[str] = []
            longest_server = max(
                len(self.catalog.by_server[server]) for server in servers
            )
            for offset in range(longest_server):
                for server in servers:
                    documents = self.catalog.by_server[server]
                    if offset < len(documents):
                        fallback_names.append(documents[offset].name)
                    if len(fallback_names) >= LOCAL_ROUTER_CATALOG_LIMIT:
                        break
                if len(fallback_names) >= LOCAL_ROUTER_CATALOG_LIMIT:
                    break
            candidate_names = [*routed_names, *lexical_names, *fallback_names]
            candidate_names = list(dict.fromkeys(candidate_names))[
                :LOCAL_ROUTER_CATALOG_LIMIT
            ]
            if not candidate_names:
                return []
            compact_index = self.catalog.compact_signatures(
                candidate_names,
                limit=LOCAL_ROUTER_CATALOG_LIMIT,
            )
            tool_schema = {
                "title": "select_mcp_tools",
                "type": "object",
                "properties": {
                    "tools": {
                        "type": "array",
                        "items": {"type": "string", "enum": candidate_names},
                        "maxItems": LOCAL_PREFETCH_LIMIT,
                    }
                },
                "required": ["tools"],
                "additionalProperties": False,
            }
            intent_text = "; ".join(intents) if intents else query[:500]
            tool_prompt = (
                "Select the smallest set of exact tool names that covers every "
                "intent. Prefer one tool per intent and return no speculative tools."
                f"\n\nIntents: {intent_text}\n\nCandidate signatures:\n"
                f"{compact_index}"
            )
            chosen = await self.model.with_structured_output(tool_schema).ainvoke(
                [
                    SystemMessage(tool_prompt),
                    HumanMessage(query[:2000]),
                ],
                config={
                    "metadata": {
                        "lc_source": "auxilia_tool_router",
                        **internal_call_metadata(),
                    }
                },
            )
        except Exception:  # noqa: BLE001 — discovery degrades to its visible search tool
            logger.warning("Precision discovery compact router failed", exc_info=True)
            return []
        if not isinstance(chosen, dict):
            return []
        allowed = set(candidate_names)
        return list(
            dict.fromkeys(
                name
                for name in chosen.get("tools", [])
                if isinstance(name, str) and name in allowed
            )
        )[:LOCAL_PREFETCH_LIMIT]

    def _search(
        self,
        runtime: ToolRuntime,
        query: str = "",
        server: str | None = None,
        offset: int = 0,
        limit: int = LOCAL_RESULT_LIMIT,
    ) -> Command:
        safe_offset = max(0, offset)
        safe_limit = max(1, min(limit, LOCAL_RESULT_LIMIT))
        resolved_server = next(
            (
                name
                for name in self.catalog.by_server
                if server is not None and name.casefold() == server.strip().casefold()
            ),
            None,
        )
        result = self.catalog.search(
            query,
            limit=safe_offset + safe_limit,
            servers=(
                {resolved_server}
                if resolved_server is not None
                else set()
                if server is not None
                else None
            ),
        )
        page = result.hits[safe_offset : safe_offset + safe_limit]
        documents = [hit.document for hit in page]
        total = result.total_hits
        browsed = False
        if not documents and server is not None:
            resolved_browse_server = server
            documents = list(
                self.catalog.browse(
                    server=resolved_browse_server,
                    offset=safe_offset,
                    limit=safe_limit,
                )
            )
            total = (
                len(self.catalog.by_server[resolved_server])
                if resolved_server is not None
                else 0
            )
            browsed = True
        lines = [f"- {document.compact_signature}" for document in documents]
        if lines:
            content = (
                f"Found {total} candidate MCP tools; showing "
                f"{safe_offset + 1}-{safe_offset + len(documents)}:\n"
                + "\n".join(lines)
            )
            if safe_offset + len(documents) < total:
                content += (
                    f"\nMore candidates are available with offset="
                    f"{safe_offset + len(documents)}."
                )
        else:
            content = "No matching MCP tools found. Try a broader search query."
        selected = (
            [hit.document.name for hit in self._prefetch_hits(page)[:2]]
            if result.confident and safe_offset == 0 and not browsed
            else []
        )
        if selected:
            content += (
                "\nLoaded for the next step: "
                + ", ".join(selected)
                + ". Load another candidate only if needed."
            )
        elif documents:
            content += (
                f"\nNo schema was auto-loaded. Use {self.load_tool_name} with exact "
                "names from this list."
            )
        candidate_names = [document.name for document in documents]
        logger.info(
            "Precision discovery manual query candidates=%d selected=%d confident=%s",
            len(candidate_names),
            len(selected),
            result.confident,
        )
        return Command(
            update={
                LOCAL_DISCOVERY_STATE_KEY: selected,
                LOCAL_DISCOVERY_CANDIDATES_KEY: candidate_names,
                "messages": [
                    ToolMessage(
                        content=content,
                        tool_call_id=runtime.tool_call_id or "",
                        name=self.search_tool_name,
                    )
                ],
            }
        )

    def _load(self, names: list[str], runtime: ToolRuntime) -> Command:
        candidates = _candidate_tool_names(runtime.state)
        loaded = [
            name
            for name in dict.fromkeys(names)
            if name in candidates and name in self.searchable_tool_names
        ][:LOCAL_VISIBLE_LIMIT]
        rejected = [name for name in names if name not in loaded]
        if loaded:
            content = "Loaded MCP tool schemas: " + ", ".join(loaded) + "."
        else:
            content = (
                f"No tools loaded. Call {self.search_tool_name} first, then pass "
                "exact names from its latest result."
            )
        if rejected:
            content += " Ignored names outside the latest search results."
        logger.info(
            "Precision discovery explicit load requested=%d loaded=%d",
            len(names),
            len(loaded),
        )
        return Command(
            update={
                LOCAL_DISCOVERY_STATE_KEY: loaded,
                "messages": [
                    ToolMessage(
                        content=content,
                        tool_call_id=runtime.tool_call_id or "",
                        name=self.load_tool_name,
                        status="success" if loaded else "error",
                    )
                ],
            }
        )

    def _hidden_tool_hint(self, name: str) -> str:
        return (
            f"Tool '{name}' is not loaded. Call {self.search_tool_name}, use "
            f"{self.load_tool_name} if needed, then invoke it on the next step."
        )


HIDDEN_SCHEMA_MODES: frozenset[ToolDiscoveryMode] = frozenset(
    {ToolDiscoveryMode.lazy, ToolDiscoveryMode.local}
)


def discovery_interrupt_on(
    interrupt_on: dict[str, bool] | None,
    mode: ToolDiscoveryMode,
) -> dict[str, bool | InterruptOnConfig] | None:
    """Gate approvals on hidden-schema modes to tools that are visible: a
    call to a hidden tool is answered by the discovery error, so asking the
    user to approve it first would be noise."""
    if interrupt_on is None or mode not in HIDDEN_SCHEMA_MODES:
        return cast(dict[str, bool | InterruptOnConfig] | None, interrupt_on)

    def is_discovered(request: ToolCallRequest) -> bool:
        selected = _selected_tool_names(request.state)
        return request.tool_call["name"] in selected

    return {
        name: InterruptOnConfig(
            allowed_decisions=["approve", "edit", "reject", "respond"],
            when=is_discovered,
        )
        for name, enabled in interrupt_on.items()
        if enabled
    }


def tool_discovery_middleware(
    *,
    model,
    searchable_tools: list[BaseTool],
    mode: ToolDiscoveryMode,
    catalog: ToolCatalog | None = None,
    server_context: str | None = None,
    server_descriptions: Mapping[str, str | None] | None = None,
    router_model=None,
) -> HiddenSchemaMiddleware | None:
    """Build the configured discovery strategy for one runnable.

    ``router_model`` is the minimal-effort variant of ``model`` the lazy
    router calls; it falls back to ``model`` when the provider has no cheaper
    setting.
    """
    if mode is ToolDiscoveryMode.disabled or not searchable_tools:
        return None
    if mode is ToolDiscoveryMode.local:
        return LocalToolDiscoveryMiddleware(
            searchable_tools,
            model=model,
            catalog=catalog,
            server_context=server_context,
        )
    return LazyToolDiscoveryMiddleware(
        searchable_tools,
        model=router_model if router_model is not None else model,
        server_descriptions=server_descriptions,
    )
