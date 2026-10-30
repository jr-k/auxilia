from collections.abc import Callable
from typing import Any
from uuid import UUID


class ChannelProtocolAdapter:
    """Project root-agent protocol events into side-channel text and artifacts."""

    def __init__(
        self,
        *,
        show_tool_callouts: bool = True,
        format_tool: Callable[[str], str] | None = None,
    ) -> None:
        self._show_tool_callouts = show_tool_callouts
        self._format_tool = format_tool or (
            lambda name: f"\n\nRunning {name.replace('_', ' ')}...\n\n"
        )
        self._tools_started: set[str] = set()
        self._tools_announced: set[str] = set()
        self._open_role: dict[str, str] = {}
        self.artifact_ids: list[UUID] = []
        self._artifact_ids_seen: set[UUID] = set()

    def texts(self, event: dict[str, Any]) -> list[str]:
        params = event.get("params") or {}
        data = params.get("data")
        if not isinstance(data, dict):
            return []
        self._capture_artifacts(event.get("method"), data)
        if params.get("namespace"):
            return []
        method = event.get("method")
        if method == "messages":
            return self._on_message(str(params.get("node") or ""), data)
        if (
            self._show_tool_callouts
            and method == "tools"
            and data.get("event") == "tool-started"
        ):
            tool_call_id = data.get("tool_call_id")
            tool_name = data.get("tool_name")
            normalized = str(tool_name or "")
            if (
                tool_call_id
                and normalized
                and tool_call_id not in self._tools_started
                and normalized not in self._tools_announced
            ):
                self._tools_started.add(str(tool_call_id))
                self._tools_announced.add(normalized)
                return [self._format_tool(normalized)]
        return []

    def _capture_artifacts(self, method: Any, data: dict[str, Any]) -> None:
        if method != "tools" or data.get("event") != "tool-finished":
            return
        output = data.get("output")
        artifact = output.get("artifact") if isinstance(output, dict) else None
        items = (
            artifact.get("auxilia_artifacts") if isinstance(artifact, dict) else None
        )
        if not isinstance(items, list):
            return
        for item in items:
            raw_id = item.get("id") if isinstance(item, dict) else None
            try:
                artifact_id = UUID(raw_id) if isinstance(raw_id, str) else None
            except ValueError:
                artifact_id = None
            if artifact_id is None or artifact_id in self._artifact_ids_seen:
                continue
            self._artifact_ids_seen.add(artifact_id)
            self.artifact_ids.append(artifact_id)

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
