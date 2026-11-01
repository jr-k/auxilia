"""Push delivery — the seam between a run and a non-HTTP recipient.

Most runs are *pulled*: an HTTP subscriber rides the event log (a protocol
event-stream session, `POST /threads/{id}/stream/events`). A push channel (e.g.
Slack) has no client connection to ride, so its updates are delivered by a
worker-side consumer that subscribes to the run's event log and relays each
event to the channel.

This module stays channel-agnostic: it defines the consumer shape, factory type,
and composition helper. The composition root (`main.py`) injects concrete
factories, so `app/runtime/runs` never imports `app/integrations`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.runtime.runs.models import RunDB


class DeliveryConsumer(Protocol):
    """Relays a run's event log to a push channel, end to end."""

    async def run(self) -> None: ...


# Built once per run from its record; returns `None` when the record has no push
# delivery (the common case — a pull subscriber handles it instead).
DeliveryFactory = Callable[[RunDB], DeliveryConsumer | None]


def compose_delivery_factories(
    *factories: DeliveryFactory,
) -> DeliveryFactory:
    """Route each push-bound run to exactly one channel consumer."""

    def build(record: RunDB) -> DeliveryConsumer | None:
        matches = [consumer for factory in factories if (consumer := factory(record))]
        if len(matches) > 1:
            raise RuntimeError(
                f"Multiple delivery consumers matched run {record.id}: "
                f"{len(matches)} factories"
            )
        return matches[0] if matches else None

    return build


class RuntimeToolBundle(Protocol):
    """Integration-owned tools and their run-local approval policy."""

    tools: Sequence[BaseTool]
    interrupt_on: dict[str, bool] | None


class RuntimeToolFactory(Protocol):
    """Build run-local tools without coupling the runtime to an integration."""

    async def __call__(
        self,
        db: AsyncSession,
        delivery: dict[str, Any] | None,
        *,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
    ) -> RuntimeToolBundle: ...


@dataclass(frozen=True)
class CombinedRuntimeToolBundle:
    tools: tuple[BaseTool, ...] = ()
    interrupt_on: dict[str, bool] | None = None


def compose_runtime_tool_factories(
    *factories: RuntimeToolFactory,
) -> RuntimeToolFactory:
    """Combine independent integration tools into one run-local bundle."""

    async def build(
        db: AsyncSession,
        delivery: dict[str, Any] | None,
        *,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
    ) -> CombinedRuntimeToolBundle:
        tools: list[BaseTool] = []
        interrupt_on: dict[str, bool] = {}
        names: set[str] = set()
        for factory in factories:
            resolved = await factory(
                db,
                delivery,
                workspace_id=workspace_id,
                agent_id=agent_id,
                user_id=user_id,
            )
            for item in resolved.tools:
                if item.name in names:
                    raise RuntimeError(f"Duplicate runtime tool name: {item.name}")
                names.add(item.name)
                tools.append(item)
            interrupt_on.update(resolved.interrupt_on or {})
        return CombinedRuntimeToolBundle(tuple(tools), interrupt_on)

    return cast(RuntimeToolFactory, build)
