"""Tool selection policies for large OpenAI MCP graphs."""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import LLMToolSelectorMiddleware


logger = logging.getLogger(__name__)

TOOL_SELECTION_PROMPT = (
    "Select the smallest set of tools needed to answer the user's query. "
    "Return only exact tool names from the provided enum. Prefer tools whose "
    "server-name prefix matches the requested service."
)


class LenientLLMToolSelectorMiddleware(LLMToolSelectorMiddleware):
    """Ignore hallucinated names while preserving the selector's valid choices.

    Some compact models satisfy the structured response shape but still return
    tool names outside its enum. The upstream middleware raises on any such
    name, discarding valid selections from the same response.
    """

    def __init__(self, *, model, max_tools: int) -> None:
        super().__init__(
            model=model,
            system_prompt=TOOL_SELECTION_PROMPT,
            max_tools=max_tools,
        )

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
        filtered = [name for name in selected if name in valid_names]
        dropped = len(selected) - len(filtered)
        if dropped:
            logger.warning("Ignored %d invalid tool selector choice(s)", dropped)
        return super()._process_selection_response(
            {"tools": filtered},
            available_tools,
            valid_tool_names,
            request,
            apply_max_tools=apply_max_tools,
        )
