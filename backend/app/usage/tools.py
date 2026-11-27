"""Which MCP server or skill each tool call of a model call belongs to.

A model call's cost is split evenly between the tool calls it made; each
server and skill gets the share of its calls. Live recording and the history
import resolve owners the same way, from the workspace's current servers and
skills, since checkpoints only keep tool names and arguments.
"""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage

from app.runtime.toolset import sanitize_tool_name
from app.skills.middleware import SKILLS_ROOT
from app.usage.repository import UsageDimension


_SKILL_PATH = re.compile(re.escape(SKILLS_ROOT) + r"/([^/\s'\"`]+)")


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _strings(item)


@dataclass(frozen=True)
class ToolOwners:
    """A workspace's MCP servers and skills, as tool calls name them."""

    # (tool-name prefix, server id), longest prefix first.
    server_prefixes: tuple[tuple[str, UUID], ...] = ()
    skill_ids: dict[str, UUID] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        servers: Iterable[tuple[UUID, str]],
        skills: Iterable[tuple[UUID, str]],
    ) -> ToolOwners:
        prefixes = sorted(
            (
                (f"{sanitize_tool_name(name)}_", server_id)
                for server_id, name in servers
            ),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )
        return cls(
            server_prefixes=tuple(prefixes),
            skill_ids={name: skill_id for skill_id, name in skills},
        )

    def server_of(self, tool_name: str) -> UUID | None:
        """MCP tools are bound as ``{server}_{tool}``, sanitized."""
        for prefix, server_id in self.server_prefixes:
            if tool_name.startswith(prefix):
                return server_id
        return None

    def skill_of(self, args: Any) -> UUID | None:
        """The skill whose folder the call reads, lists or runs a file of."""
        for text in _strings(args):
            for name in _SKILL_PATH.findall(text):
                if (skill_id := self.skill_ids.get(name)) is not None:
                    return skill_id
        return None


def tool_shares(message: AIMessage, owners: ToolOwners) -> list[dict[str, Any]]:
    """Each owner's share of the call, per dimension. Tools outside any server
    or skill share the NULL key, so a call's shares add up to 1."""
    calls = message.tool_calls
    if not calls:
        return []
    total = Decimal(len(calls))
    counts = {
        UsageDimension.mcp: Counter(owners.server_of(call["name"]) for call in calls),
        UsageDimension.skill: Counter(
            owners.skill_of(call.get("args")) for call in calls
        ),
    }
    return [
        {
            "dimension": dimension.value,
            "key": key,
            "weight": count / total,
            "tool_calls": count,
        }
        for dimension, by_key in counts.items()
        for key, count in by_key.items()
    ]
