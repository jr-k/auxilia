"""Keep persisted MCP file results compatible with model providers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import HumanMessage, ToolMessage

from app.mcp.client.tools import normalize_mcp_tool_content


class MCPContentCompatibilityMiddleware(AgentMiddleware):
    """Normalize persisted content blocks before each model request."""

    @staticmethod
    def _normalize_request(request: ModelRequest) -> ModelRequest:
        changed = False
        messages: list[Any] = []
        for message in request.messages:
            text_blocks: list[dict[str, Any]] = []
            if isinstance(message, HumanMessage) and isinstance(message.content, list):
                text_blocks = [
                    block
                    for block in message.content
                    if isinstance(block, dict)
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                ]
            if (
                isinstance(message, HumanMessage)
                and isinstance(message.content, list)
                and message.additional_kwargs.get("inline_text_files")
                and len(text_blocks) == len(message.content)
            ):
                changed = True
                messages.append(
                    message.model_copy(
                        update={
                            "content": "\n\n".join(
                                block["text"] for block in text_blocks
                            )
                        }
                    )
                )
                continue
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
