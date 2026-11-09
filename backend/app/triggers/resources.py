from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.repository import AgentRepository
from app.agents.run_spec import RunSpec
from app.realtime.schemas import WorkspaceEventKind
from app.realtime.service import stage_workspace_event
from app.skills.repository import SkillRepository
from app.triggers.repository import TriggerRepository


ResourceField = Literal[
    "disabled_mcp_server_ids",
    "disabled_skill_ids",
    "disabled_sandbox_ids",
    "disabled_subagent_ids",
]

RESOURCE_FIELDS: tuple[ResourceField, ...] = (
    "disabled_mcp_server_ids",
    "disabled_skill_ids",
    "disabled_sandbox_ids",
    "disabled_subagent_ids",
)


@dataclass(frozen=True)
class ResourceState:
    available: frozenset[UUID]
    disabled_by_default: frozenset[UUID]


@dataclass(frozen=True)
class AgentGraphResourceSnapshot:
    resources: dict[ResourceField, ResourceState]


TriggerResourceSnapshot = dict[UUID, AgentGraphResourceSnapshot]


class TriggerResourceService:
    """Keep existing triggers narrower when an agent graph gains resources."""

    def __init__(
        self,
        db: AsyncSession,
        workspace_id: UUID | None,
        *,
        agents: AgentRepository | None = None,
        skills: SkillRepository | None = None,
    ):
        self.db = db
        self.workspace_id = workspace_id
        self.agents = agents or AgentRepository(db, workspace_id)
        self.skills = skills or SkillRepository(db, workspace_id)
        self.triggers = TriggerRepository(db, workspace_id)

    async def capture_affected(self, agent_id: UUID) -> TriggerResourceSnapshot:
        if self.workspace_id is None:
            return {}
        agent_snapshot = await self._capture_graph(agent_id)
        if agent_snapshot is None:
            return {}
        root_ids = {agent_id}
        links = await self.agents.list_subagent_links_for_agents([agent_id])
        root_ids.update(
            link.supervisor_id for link in links if link.subagent_id == agent_id
        )
        snapshots: TriggerResourceSnapshot = {agent_id: agent_snapshot}
        for root_id in sorted(root_ids - {agent_id}, key=str):
            snapshot = await self._capture_graph(root_id)
            if snapshot is not None:
                snapshots[root_id] = snapshot
        return snapshots

    async def preserve_additions(self, before: TriggerResourceSnapshot) -> None:
        if self.workspace_id is None or not before:
            return
        changed = False
        projects_changed = False
        for agent_id, previous in before.items():
            current = await self._capture_graph(agent_id)
            if current is None:
                continue
            additions = {
                field: (
                    current.resources[field].available
                    - previous.resources[field].available
                )
                for field in RESOURCE_FIELDS
            }
            if not any(additions.values()):
                continue
            triggers = await self.triggers.list_for_agent_for_update(agent_id)
            for trigger in triggers:
                trigger_changed = False
                for field, added_ids in additions.items():
                    if not added_ids:
                        continue
                    stored = getattr(trigger, field)
                    if stored is None:
                        values = sorted(
                            current.resources[field].disabled_by_default | added_ids,
                            key=str,
                        )
                        serialized = [str(resource_id) for resource_id in values]
                    else:
                        serialized = list(dict.fromkeys(stored))
                        known = set(serialized)
                        serialized.extend(
                            resource_id
                            for resource_id in sorted(
                                str(resource_id) for resource_id in added_ids
                            )
                            if resource_id not in known
                        )
                    if stored != serialized:
                        setattr(trigger, field, serialized)
                        trigger_changed = True
                if trigger_changed:
                    self.db.add(trigger)
                    changed = True
                    projects_changed = (
                        projects_changed or trigger.project_id is not None
                    )
        if not changed:
            return
        await self.db.flush()
        await stage_workspace_event(
            self.db,
            workspace_id=self.workspace_id,
            kind=WorkspaceEventKind.triggers,
        )
        if projects_changed:
            await stage_workspace_event(
                self.db,
                workspace_id=self.workspace_id,
                kind=WorkspaceEventKind.projects,
            )

    async def _capture_graph(self, agent_id: UUID) -> AgentGraphResourceSnapshot | None:
        spec = await self.agents.get_run_spec(agent_id)
        if spec is None:
            return None
        skill_ids = await self.skills.list_attached_ids_for_agents(spec.all_agent_ids)
        disabled_skill_ids = await self.skills.list_disabled_by_default_ids_for_agents(
            spec.all_agent_ids
        )
        return AgentGraphResourceSnapshot(
            resources={
                "disabled_mcp_server_ids": ResourceState(
                    available=frozenset(
                        binding.mcp_server_id for binding in spec.all_mcp_bindings
                    ),
                    disabled_by_default=frozenset(
                        binding.mcp_server_id
                        for binding in spec.all_mcp_bindings
                        if not binding.enabled_by_default
                    ),
                ),
                "disabled_skill_ids": ResourceState(
                    available=frozenset(skill_ids),
                    disabled_by_default=frozenset(disabled_skill_ids),
                ),
                "disabled_sandbox_ids": self._sandbox_state(spec),
                "disabled_subagent_ids": ResourceState(
                    available=frozenset(subagent.id for subagent in spec.subagents),
                    disabled_by_default=frozenset(
                        subagent.id
                        for subagent in spec.subagents
                        if not subagent.enabled_by_default
                    ),
                ),
            }
        )

    @staticmethod
    def _sandbox_state(spec: RunSpec) -> ResourceState:
        sandboxes = [
            agent_spec.sandbox
            for agent_spec in [spec.agent, *spec.subagents]
            if agent_spec.sandbox is not None
        ]
        return ResourceState(
            available=frozenset(sandbox.row.id for sandbox in sandboxes),
            disabled_by_default=frozenset(
                sandbox.row.id
                for sandbox in sandboxes
                if not sandbox.enabled_by_default
            ),
        )
