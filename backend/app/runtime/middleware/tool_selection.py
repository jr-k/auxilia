"""Provider-native and model-driven MCP tool discovery."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated, Any, cast

from langchain.agents.middleware import (
    AgentMiddleware,
    LLMToolSelectorMiddleware,
    ProviderToolSearchMiddleware,
)
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
from app.runtime.tool_catalog import SearchHit, ToolCatalog


logger = logging.getLogger(__name__)

LOCAL_DISCOVERY_STATE_KEY = "selected_mcp_tools"
LOCAL_DISCOVERY_CANDIDATES_KEY = "mcp_tool_candidates"
LOCAL_PREFETCH_LIMIT = 4
LOCAL_VISIBLE_LIMIT = 6
LOCAL_RESULT_LIMIT = 6
LOCAL_ROUTER_SERVER_LIMIT = 3
LOCAL_ROUTER_CATALOG_LIMIT = 48

TOOL_SELECTION_PROMPT = (
    "Select the smallest set of tools needed to answer the user's query. "
    "Return only exact tool names from the provided enum. All tools remain "
    "available through this discovery step, so do not list unrelated tools. "
    "Prefer tools whose server-name prefix matches the requested service."
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


class LocalToolDiscoveryMiddleware(AgentMiddleware[LocalToolDiscoveryState]):
    """Prefetch a tiny MCP schema set, with compact adaptive widening."""

    state_schema = LocalToolDiscoveryState
    transformers = (InternalCallTransformer,)

    def __init__(
        self,
        searchable_tools: list[BaseTool],
        *,
        model,
        catalog: ToolCatalog | None = None,
        server_context: str | None = None,
    ) -> None:
        self.model = model
        self.server_context = server_context
        self.searchable_tools = list(searchable_tools)
        self.catalog = catalog or ToolCatalog(self.searchable_tools)
        self.searchable_tool_names = self.catalog.names
        search_name = "search_mcp_tools"
        suffix = 2
        while search_name in self.searchable_tool_names:
            search_name = f"search_mcp_tools_{suffix}"
            suffix += 1
        load_name = "load_mcp_tools"
        suffix = 2
        reserved_names = {*self.searchable_tool_names, search_name}
        while load_name in reserved_names:
            load_name = f"load_mcp_tools_{suffix}"
            suffix += 1
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
        query = self._last_human_text(state)
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
            "Auxilia Search prefetch route=%s candidates=%d selected=%d margin=%.3f",
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
            logger.warning("Auxilia Search compact router failed", exc_info=True)
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
            "Auxilia Search manual query candidates=%d selected=%d confident=%s",
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
            "Auxilia Search explicit load requested=%d loaded=%d",
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
            content=(
                f"Tool '{name}' is not loaded. Call {self.search_tool_name}, use "
                f"{self.load_tool_name} if needed, then invoke it on the next step."
            ),
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


def discovery_interrupt_on(
    interrupt_on: dict[str, bool] | None,
    mode: ToolDiscoveryMode,
) -> dict[str, bool | InterruptOnConfig] | None:
    """Gate local-mode approvals only after the tool schema was discovered."""
    if interrupt_on is None or mode is not ToolDiscoveryMode.local:
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


class LenientLLMToolSelectorMiddleware(LLMToolSelectorMiddleware):
    """Discover MCP tools with a model while preserving all control tools.

    Some compact models satisfy the structured response shape but still return
    tool names outside its enum. The upstream middleware raises on any such
    name, discarding valid selections from the same response. Invalid names are
    ignored here; an empty valid selection fails open to the complete MCP set.
    """

    def __init__(self, *, model, searchable_tools: list[str]) -> None:
        self.searchable_tool_names = frozenset(searchable_tools)
        super().__init__(
            model=model,
            system_prompt=TOOL_SELECTION_PROMPT,
            max_tools=None,
            on_parsing_failure="all",
        )

    def _partition_tools(
        self, request: ModelRequest
    ) -> tuple[ModelRequest, list[BaseTool | dict[str, Any]]] | None:
        discoverable: list[BaseTool | dict[str, Any]] = [
            tool
            for tool in request.tools
            if isinstance(tool, BaseTool) and tool.name in self.searchable_tool_names
        ]
        if not discoverable:
            return None
        passthrough = [
            tool
            for tool in request.tools
            if not (
                isinstance(tool, BaseTool) and tool.name in self.searchable_tool_names
            )
        ]
        return request.override(tools=discoverable), passthrough

    @staticmethod
    def _restore_tools(
        request: ModelRequest,
        passthrough: list[BaseTool | dict[str, Any]],
    ) -> ModelRequest:
        return request.override(tools=[*request.tools, *passthrough])

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | AIMessage:
        partitioned = self._partition_tools(request)
        if partitioned is None:
            return handler(request)
        selection_request, passthrough = partitioned

        def restore_and_call(selected: ModelRequest):
            return handler(self._restore_tools(selected, passthrough))

        return super().wrap_model_call(selection_request, restore_and_call)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse | AIMessage:
        partitioned = self._partition_tools(request)
        if partitioned is None:
            return await handler(request)
        selection_request, passthrough = partitioned

        async def restore_and_call(selected: ModelRequest):
            return await handler(self._restore_tools(selected, passthrough))

        return await super().awrap_model_call(selection_request, restore_and_call)

    def _process_selection_response(
        self,
        response: dict[str, Any],
        available_tools: list,
        valid_tool_names: list[str],
        request,
        *,
        apply_max_tools: bool = True,
    ):
        valid_names = set(valid_tool_names)
        selected = response.get("tools", [])
        filtered = [
            name for name in selected if isinstance(name, str) and name in valid_names
        ]
        dropped = len(selected) - len(filtered)
        if dropped:
            logger.warning("Ignored %d invalid tool selector choice(s)", dropped)
        if not filtered:
            logger.info(
                "Tool selector returned no valid choices; exposing all MCP tools"
            )
            filtered = valid_tool_names
        return super()._process_selection_response(
            {"tools": filtered},
            available_tools,
            valid_tool_names,
            request,
            apply_max_tools=apply_max_tools,
        )


def tool_discovery_middleware(
    *,
    model,
    searchable_tools: list[BaseTool],
    mode: ToolDiscoveryMode,
    provider_native: bool,
    catalog: ToolCatalog | None = None,
    server_context: str | None = None,
):
    """Build the configured discovery strategy for one runnable."""
    if mode is ToolDiscoveryMode.disabled or not searchable_tools:
        return None
    if mode is ToolDiscoveryMode.local:
        return LocalToolDiscoveryMiddleware(
            searchable_tools,
            model=model,
            catalog=catalog,
            server_context=server_context,
        )
    searchable_tool_names = [tool.name for tool in searchable_tools]
    if provider_native:
        provider_tools: list[str | BaseTool] = list(searchable_tool_names)
        return ProviderToolSearchMiddleware(searchable_tools=provider_tools)
    return LenientLLMToolSelectorMiddleware(
        model=model,
        searchable_tools=searchable_tool_names,
    )
