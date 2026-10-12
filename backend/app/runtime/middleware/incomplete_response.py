"""Keep provider-incomplete model turns visible to the user."""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime


logger = logging.getLogger(__name__)

OUTPUT_LIMIT_MESSAGE = (
    "The model reached its output limit before producing an answer. "
    "Please retry, lower the reasoning effort, or choose another model."
)
INCOMPLETE_MESSAGE = (
    "The model stopped before producing an answer. Please retry or choose "
    "another model."
)


def _has_visible_output(message: AIMessage) -> bool:
    if message.tool_calls or message.invalid_tool_calls:
        return True
    if isinstance(message.content, str):
        return bool(message.content.strip())
    return any(
        isinstance(block, dict)
        and block.get("type") == "text"
        and str(block.get("text", "")).strip()
        for block in message.content
    )


class IncompleteResponseMiddleware(AgentMiddleware):
    """Replace an invisible incomplete response with a user-facing notice.

    OpenAI's Responses API can return ``status=incomplete`` without raising,
    including an entirely empty message when the output budget is exhausted.
    LangGraph otherwise treats that as a successful terminal turn.
    """

    def after_model(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        messages = state["messages"]
        if not messages:
            return None
        last = messages[-1]
        if (
            not isinstance(last, AIMessage)
            or last.response_metadata.get("status") != "incomplete"
            or _has_visible_output(last)
        ):
            return None

        details = last.response_metadata.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else None
        logger.warning(
            "Model returned an empty incomplete response for message %s: %s",
            last.id,
            reason or "unknown reason",
        )
        content = (
            OUTPUT_LIMIT_MESSAGE
            if reason == "max_output_tokens"
            else INCOMPLETE_MESSAGE
        )
        return {"messages": [last.model_copy(update={"content": content})]}
