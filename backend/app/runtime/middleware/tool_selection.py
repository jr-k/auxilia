"""Provider-native and model-driven MCP tool discovery."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated, Any, cast

from langchain.agents.middleware import (
    AgentMiddleware,
    LLMToolSelectorMiddleware,
    ProviderToolSearchMiddleware,
)
from langchain.agents.middleware.human_in_the_loop import InterruptOnConfig
from langchain.agents.middleware.types import (
    AgentState,
    ModelRequest,
    ModelResponse,
    PrivateStateAttr,
    ToolCallRequest,
)
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command, Overwrite

from app.agents.models import ToolDiscoveryMode


logger = logging.getLogger(__name__)

LOCAL_DISCOVERY_STATE_KEY = "selected_mcp_tools"
LOCAL_SEARCH_PAGE_SIZE = 10
LOCAL_SEARCH_MAX_PAGE_SIZE = 20

TOOL_SELECTION_PROMPT = (
    "Select the smallest set of tools needed to answer the user's query. "
    "Return only exact tool names from the provided enum. All tools remain "
    "available through this discovery step, so do not list unrelated tools. "
    "Prefer tools whose server-name prefix matches the requested service."
)


def _merge_tool_names(left: list[str], right: list[str] | Overwrite) -> list[str]:
    if isinstance(right, Overwrite):
        return list(right.value)
    return list(dict.fromkeys([*left, *right]))


class LocalToolDiscoveryState(AgentState[Any], total=False):
    selected_mcp_tools: Annotated[
        list[str],
        _merge_tool_names,
        PrivateStateAttr,
    ]


def _search_tokens(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", value.casefold())


def _selected_tool_names(state: Mapping[str, Any]) -> frozenset[str]:
    raw = state.get(LOCAL_DISCOVERY_STATE_KEY, [])
    if isinstance(raw, Overwrite):
        raw = raw.value
    return frozenset(cast(list[str], raw))


class LocalToolDiscoveryMiddleware(AgentMiddleware[LocalToolDiscoveryState]):
    """Expose MCP schemas only after a deterministic local catalog search."""

    state_schema = LocalToolDiscoveryState

    def __init__(self, searchable_tools: list[BaseTool]) -> None:
        self.searchable_tools = list(searchable_tools)
        self.searchable_tool_names = frozenset(tool.name for tool in searchable_tools)
        search_name = "search_mcp_tools"
        suffix = 2
        while search_name in self.searchable_tool_names:
            search_name = f"search_mcp_tools_{suffix}"
            suffix += 1
        self.search_tool_name = search_name
        self.tools = [
            StructuredTool.from_function(
                func=self._search,
                name=search_name,
                description=(
                    "Search the enabled MCP tool catalog locally. Call this before "
                    "using an MCP capability whose schema is not visible. Matching "
                    "tool schemas become available on the next model step. Results "
                    "are ranked and paginated; use offset to inspect later pages."
                ),
            )
        ]

    def before_agent(self, state: LocalToolDiscoveryState, runtime) -> dict[str, Any]:
        return {LOCAL_DISCOVERY_STATE_KEY: Overwrite([])}

    def _ranked(self, query: str) -> list[BaseTool]:
        cleaned = " ".join(query[:500].split()).casefold()
        query_tokens = set(_search_tokens(cleaned))
        if not cleaned or not query_tokens:
            return []

        ranked: list[tuple[int, int, BaseTool]] = []
        for position, candidate in enumerate(self.searchable_tools):
            name = candidate.name.casefold()
            description = (candidate.description or "")[:2000].casefold()
            name_tokens = set(_search_tokens(name))
            description_tokens = set(_search_tokens(description))
            score = 0
            if cleaned == name:
                score += 1000
            elif name.startswith(cleaned):
                score += 400
            elif cleaned in name:
                score += 250
            score += 40 * len(query_tokens & name_tokens)
            score += 5 * len(query_tokens & description_tokens)
            if score:
                ranked.append((-score, position, candidate))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [candidate for _, _, candidate in ranked]

    def _search(
        self,
        query: str,
        runtime: ToolRuntime,
        offset: int = 0,
        limit: int = LOCAL_SEARCH_PAGE_SIZE,
    ) -> Command:
        ranked = self._ranked(query)
        safe_offset = max(0, offset)
        safe_limit = max(1, min(limit, LOCAL_SEARCH_MAX_PAGE_SIZE))
        page = ranked[safe_offset : safe_offset + safe_limit]
        lines = [
            f"- {candidate.name}: {' '.join((candidate.description or '').split())[:300]}"
            for candidate in page
        ]
        if lines:
            content = (
                f"Found {len(ranked)} matching MCP tools; showing "
                f"{safe_offset + 1}-{safe_offset + len(page)}:\n" + "\n".join(lines)
            )
            if safe_offset + len(page) < len(ranked):
                content += (
                    f"\nMore results are available with offset="
                    f"{safe_offset + len(page)}."
                )
        else:
            content = "No matching MCP tools found. Try a broader search query."
        return Command(
            update={
                LOCAL_DISCOVERY_STATE_KEY: [candidate.name for candidate in page],
                "messages": [
                    ToolMessage(
                        content=content,
                        tool_call_id=runtime.tool_call_id or "",
                        name=self.search_tool_name,
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
                f"Tool '{name}' is not loaded. Call {self.search_tool_name} first "
                "and invoke the tool on the next step."
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
):
    """Build the configured discovery strategy for one runnable."""
    if mode is ToolDiscoveryMode.disabled or not searchable_tools:
        return None
    if mode is ToolDiscoveryMode.local:
        return LocalToolDiscoveryMiddleware(searchable_tools)
    searchable_tool_names = [tool.name for tool in searchable_tools]
    if provider_native:
        provider_tools: list[str | BaseTool] = list(searchable_tool_names)
        return ProviderToolSearchMiddleware(searchable_tools=provider_tools)
    return LenientLLMToolSelectorMiddleware(
        model=model,
        searchable_tools=searchable_tool_names,
    )
