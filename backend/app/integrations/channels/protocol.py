from collections.abc import Callable
from typing import Any


class ChannelProtocolAdapter:
    """Extract user-facing root-agent text and tool starts from wire events."""

    def __init__(self, format_tool: Callable[[str], str] | None = None) -> None:
        self._format_tool = format_tool or (lambda name: f"\n\nRunning `{name}`…\n\n")
        self._tools_started: set[str] = set()
        self._open_role: dict[str, str] = {}

    def texts(self, event: dict[str, Any]) -> list[str]:
        params = event.get("params") or {}
        if params.get("namespace"):
            return []
        data = params.get("data")
        if not isinstance(data, dict):
            return []
        method = event.get("method")
        if method == "messages":
            return self._on_message(str(params.get("node") or ""), data)
        if method == "tools" and data.get("event") == "tool-started":
            tool_call_id = data.get("tool_call_id")
            tool_name = data.get("tool_name")
            if tool_call_id and tool_name and tool_call_id not in self._tools_started:
                self._tools_started.add(str(tool_call_id))
                return [self._format_tool(str(tool_name))]
        return []

    def _on_message(self, node: str, data: dict[str, Any]) -> list[str]:
        kind = data.get("event")
        if kind == "message-start":
            self._open_role[node] = str(data.get("role") or "ai")
            return []
        if kind == "message-finish":
            self._open_role.pop(node, None)
            return []
        if self._open_role.get(node, "ai") != "ai":
            return []
        if kind == "content-block-start":
            content = data.get("content")
            if isinstance(content, dict) and content.get("type") == "text":
                text = content.get("text")
                return [text] if isinstance(text, str) and text else []
        if kind == "content-block-delta":
            delta = data.get("delta")
            if isinstance(delta, dict) and delta.get("type") == "text-delta":
                text = delta.get("text")
                return [text] if isinstance(text, str) and text else []
        return []
