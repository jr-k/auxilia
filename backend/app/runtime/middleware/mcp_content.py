"""Keep persisted MCP file results compatible with model providers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import ToolMessage

from app.mcp.client.tools import normalize_mcp_tool_content


class MCPContentCompatibilityMiddleware(AgentMiddleware):
    """Normalize old untyped MCP blobs before each model request."""

    @staticmethod
    def _normalize_request(request: ModelRequest) -> ModelRequest:
        changed = False
        messages: list[Any] = []
        for message in request.messages:
            if not isinstance(message, ToolMessage):
                messages.append(message)
                continue
            content = normalize_mcp_tool_content(message.content)
            if content == message.content:
                messages.append(message)
                continue
            changed = True
            messages.append(message.model_copy(update={"content": content}))
        return request.override(messages=messages) if changed else request

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(self._normalize_request(request))
