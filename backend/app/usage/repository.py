from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    ColumnElement,
    Row,
    Select,
    func,
    literal_column,
    or_,
    select,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agents.models import AgentDB
from app.mcp.servers.models import MCPServerDB
from app.projects.models import ProjectDB
from app.repository import BaseRepository
from app.skills.models import SkillDB
from app.threads.models import ThreadDB
from app.triggers.models import TriggerDB
from app.usage.models import (
    LLMUsageDB,
    LLMUsageToolShareDB,
    UsageChannel,
    UsageLedgerStateDB,
    UsageSettingsDB,
)
from app.users.models import UserDB
from app.workspaces.models import WorkspaceDB


class UsageDimension(StrEnum):
    channel = "channel"
    agent = "agent"
    project = "project"
    trigger = "trigger"
    user = "user"
    model = "model"
    # A model's creator per the catalog: grouped from `model` in the service,
    # never queried as a column.
    vendor = "vendor"
    workspace = "workspace"
    # Weighted by the tool shares of each call (`LLMUsageToolShareDB`).
    mcp = "mcp"
    skill = "skill"


TOOL_DIMENSIONS = frozenset({UsageDimension.mcp, UsageDimension.skill})


class Granularity(StrEnum):
    day = "day"
    week = "week"
    month = "month"


TRIGGER_CHANNELS = (
    UsageChannel.schedule.value,
    UsageChannel.webhook.value,
    UsageChannel.trigger.value,
)

_DIMENSION_COLUMNS: dict[UsageDimension, Any] = {
    UsageDimension.channel: LLMUsageDB.channel,
    UsageDimension.agent: LLMUsageDB.agent_id,
    UsageDimension.project: LLMUsageDB.project_id,
    UsageDimension.trigger: LLMUsageDB.trigger_id,
    UsageDimension.user: LLMUsageDB.user_id,
    UsageDimension.model: LLMUsageDB.model_id,
    UsageDimension.workspace: LLMUsageDB.workspace_id,
}


@dataclass(frozen=True)
class UsageFilter:
    """Rows a query may see. `workspace_id=None` is the whole instance."""

    workspace_id: UUID | None
    user_id: UUID | None = None
    agent_id: UUID | None = None
    project_id: UUID | None = None
    trigger_id: UUID | None = None
    channel: str | None = None
    model_id: str | None = None
    # A vendor is a set of catalog models, resolved by the service.
    vendor: str | None = None
    vendor_model_ids: tuple[str, ...] = ()

    def conditions(self) -> list[ColumnElement[bool]]:
        pairs = (
            (LLMUsageDB.workspace_id, self.workspace_id),
            (LLMUsageDB.user_id, self.user_id),
            (LLMUsageDB.agent_id, self.agent_id),
            (LLMUsageDB.project_id, self.project_id),
            (LLMUsageDB.trigger_id, self.trigger_id),
            (LLMUsageDB.channel, self.channel),
            (LLMUsageDB.model_id, self.model_id),
        )
        conditions = [
            col(column) == value for column, value in pairs if value is not None
        ]
        if self.vendor is not None:
            conditions.append(col(LLMUsageDB.model_id).in_(self.vendor_model_ids))
        return conditions


def _measures(
    window: ColumnElement[bool] | None = None, prefix: str = ""
) -> list[ColumnElement[Any]]:
    """Cost, call and token aggregates, optionally restricted to a window."""

    def scoped(expression):
        return expression.filter(window) if window is not None else expression

    def total(column):
        return func.coalesce(scoped(func.sum(column)), 0)

    unpriced = LLMUsageDB.cost_usd.is_(None)
    return [
        total(LLMUsageDB.cost_usd).label(f"{prefix}cost_usd"),
        scoped(func.count()).label(f"{prefix}calls"),
        func.count()
        .filter(unpriced if window is None else window & unpriced)
        .label(f"{prefix}unpriced_calls"),
        total(LLMUsageDB.input_tokens).label(f"{prefix}input_tokens"),
        total(LLMUsageDB.cache_read_tokens).label(f"{prefix}cache_read_tokens"),
        total(LLMUsageDB.cache_creation_tokens).label(f"{prefix}cache_creation_tokens"),
        total(LLMUsageDB.output_tokens).label(f"{prefix}output_tokens"),
        total(LLMUsageDB.total_tokens).label(f"{prefix}total_tokens"),
    ]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _in_range(
    start: datetime | None, end: datetime | None
) -> list[ColumnElement[bool]]:
    conditions = []
    if start is not None:
        conditions.append(LLMUsageDB.occurred_at >= start)
    if end is not None:
        conditions.append(LLMUsageDB.occurred_at < end)
    return conditions


class UsageRepository(BaseRepository[LLMUsageDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(LLMUsageDB, db)

    async def insert_many(self, rows: Sequence[dict[str, Any]]) -> None:
        """Insert ledger rows and their `tool_shares`; a call already recorded
        for its thread is skipped, shares included."""
        if not rows:
            return
        values = []
        shares_by_id: dict[UUID, list[dict[str, Any]]] = {}
        for row in rows:
            usage_id = uuid4()
            columns = dict(row)
            shares_by_id[usage_id] = columns.pop("tool_shares", [])
            values.append({"id": usage_id, **columns})
        stmt = (
            pg_insert(LLMUsageDB)
            .values(values)
            .on_conflict_do_nothing(constraint="uq_llm_usage_thread_message")
            .returning(col(LLMUsageDB.id))
        )
        inserted = await self.db.scalars(stmt)
        await self.insert_tool_shares(
            [
                {"usage_id": usage_id, **share}
                for usage_id in inserted
                for share in shares_by_id[usage_id]
            ]
        )

    async def insert_tool_shares(self, rows: Sequence[dict[str, Any]]) -> None:
        """Insert shares; a call's share already recorded is skipped."""
        if not rows:
            return
        stmt = (
            pg_insert(LLMUsageToolShareDB)
            .values([{"id": uuid4(), **row} for row in rows])
            .on_conflict_do_nothing(
                constraint="uq_llm_usage_tool_shares_usage_dimension_key"
            )
        )
        await self.db.execute(stmt)

    async def usage_ids_by_message(self, thread_id: str) -> dict[str, UUID]:
        stmt = select(col(LLMUsageDB.message_id), col(LLMUsageDB.id)).where(
            col(LLMUsageDB.thread_id) == thread_id,
            col(LLMUsageDB.message_id).is_not(None),
        )
        result = await self.db.execute(stmt)
        return {row.message_id: row.id for row in result}

    async def tool_owners(
        self, workspace_id: UUID
    ) -> tuple[list[tuple[UUID, str]], list[tuple[UUID, str]]]:
        """(id, name) of the workspace's MCP servers, then of its skills."""
        servers_stmt = select(col(MCPServerDB.id), col(MCPServerDB.name)).where(
            col(MCPServerDB.workspace_id) == workspace_id
        )
        skills_stmt = select(col(SkillDB.id), col(SkillDB.name)).where(
            col(SkillDB.workspace_id) == workspace_id
        )
        servers = await self.db.execute(servers_stmt)
        skills = await self.db.execute(skills_stmt)
        return (
            [(row.id, row.name) for row in servers],
            [(row.id, row.name) for row in skills],
        )

    async def totals(
        self, scope: UsageFilter, start: datetime | None, end: datetime | None
    ) -> Row:
        stmt = select(*_measures()).where(*scope.conditions(), *_in_range(start, end))
        result = await self.db.execute(stmt)
        return result.one()

    async def windowed_totals(
        self,
        scope: UsageFilter,
        windows: dict[str, datetime | None],
        group_by: UsageDimension | None = None,
        keys: Sequence[Any] | None = None,
    ) -> list[Row]:
        """One pass over the scope, aggregated per window start (None = ever).

        Columns are prefixed with the window name; grouped queries add `key`.
        """
        measures = [
            measure
            for name, start in windows.items()
            for measure in _measures(
                LLMUsageDB.occurred_at >= start if start is not None else None,
                prefix=f"{name}_",
            )
        ]
        conditions = scope.conditions()
        if group_by is None:
            stmt = select(*measures).where(*conditions)
        else:
            column = _DIMENSION_COLUMNS[group_by]
            if keys is not None:
                conditions.append(column.in_(keys))
            stmt = (
                select(column.label("key"), *measures)
                .where(*conditions)
                .group_by(column)
            )
        result = await self.db.execute(stmt)
        return list(result.all())

    async def series(
        self,
        scope: UsageFilter,
        start: datetime | None,
        end: datetime | None,
        granularity: Granularity,
        timezone: str,
    ) -> list[Row]:
        """Cost, tokens and calls per local-time bucket and channel."""
        # Literals, not binds: Postgres must see the GROUP BY expression as
        # identical to the selected one. Both values are validated upstream.
        local = func.timezone(literal_column(f"'{timezone}'"), LLMUsageDB.occurred_at)
        bucket = func.date_trunc(literal_column(f"'{granularity.value}'"), local)
        stmt = (
            select(
                bucket.label("bucket"),
                LLMUsageDB.channel.label("channel"),
                func.coalesce(func.sum(LLMUsageDB.cost_usd), 0).label("cost_usd"),
                func.coalesce(func.sum(LLMUsageDB.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.count().label("calls"),
            )
            .where(*scope.conditions(), *_in_range(start, end))
            .group_by(literal_column("bucket"), LLMUsageDB.channel)
            .order_by(literal_column("bucket"))
        )
        result = await self.db.execute(stmt)
        return list(result.all())

    async def breakdown(
        self,
        scope: UsageFilter,
        start: datetime | None,
        end: datetime | None,
        dimension: UsageDimension,
        limit: int,
    ) -> list[Row]:
        if dimension in TOOL_DIMENSIONS:
            return await self._tool_breakdown(scope, start, end, dimension, limit)
        column = _DIMENSION_COLUMNS[dimension]
        conditions = [*scope.conditions(), *_in_range(start, end)]
        if dimension is UsageDimension.trigger:
            conditions.append(LLMUsageDB.channel.in_(TRIGGER_CHANNELS))
        cost = func.coalesce(func.sum(LLMUsageDB.cost_usd), 0)
        stmt = (
            select(column.label("key"), *_measures())
            .where(*conditions)
            .group_by(column)
            .order_by(cost.desc(), func.sum(LLMUsageDB.total_tokens).desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.all())

    async def _tool_breakdown(
        self,
        scope: UsageFilter,
        start: datetime | None,
        end: datetime | None,
        dimension: UsageDimension,
        limit: int,
    ) -> list[Row]:
        """Measures weighted by each call's shares; a call without shares
        counts whole under the NULL key."""
        share = LLMUsageToolShareDB
        key = col(share.key)
        weight = func.coalesce(col(share.weight), 1)
        cost = func.coalesce(func.sum(col(LLMUsageDB.cost_usd) * weight), 0)
        tokens = func.coalesce(
            func.round(func.sum(col(LLMUsageDB.total_tokens) * weight)), 0
        )
        stmt: Select = (
            select(
                key.label("key"),
                cost.label("cost_usd"),
                func.count().label("calls"),
                func.count()
                .filter(col(LLMUsageDB.cost_usd).is_(None))
                .label("unpriced_calls"),
                tokens.label("total_tokens"),
                func.coalesce(func.sum(col(share.tool_calls)), 0).label("tool_calls"),
            )
            .select_from(LLMUsageDB)
            .outerjoin(
                share,
                (col(share.usage_id) == col(LLMUsageDB.id))
                & (col(share.dimension) == dimension.value),
            )
            .where(*scope.conditions(), *_in_range(start, end))
            .group_by(key)
            .order_by(cost.desc(), tokens.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.all())

    async def threads_created_before(
        self,
        cutoff: datetime,
        after: tuple[datetime, str] | None,
        limit: int,
    ) -> list[ThreadDB]:
        """Threads to import history from, keyset-paginated on (created_at, id)."""
        stmt = select(ThreadDB).where(ThreadDB.created_at < cutoff)
        if after is not None:
            stmt = stmt.where(tuple_(ThreadDB.created_at, ThreadDB.id) > after)
        stmt = stmt.order_by(ThreadDB.created_at, ThreadDB.id).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars())

    async def first_occurred_at(self, scope: UsageFilter) -> datetime | None:
        stmt = select(func.min(LLMUsageDB.occurred_at)).where(*scope.conditions())
        return await self.db.scalar(stmt)

    async def search_entities(
        self, scope: UsageFilter, dimension: UsageDimension, query: str, limit: int
    ) -> list[Row]:
        """Existing agents, projects, triggers or users with usage in the scope
        whose name contains `query`, by spend. Rows carry `key`, `label`, `cost_usd`."""
        column = _DIMENSION_COLUMNS[dimension]
        entity: Any
        if dimension is UsageDimension.user:
            entity = UserDB
            label = func.coalesce(UserDB.name, UserDB.email, "Unnamed user")
            searched = [col(UserDB.name), col(UserDB.email)]
        else:
            entity = {
                UsageDimension.agent: AgentDB,
                UsageDimension.project: ProjectDB,
                UsageDimension.trigger: TriggerDB,
            }[dimension]
            label = entity.name
            searched = [col(entity.name)]
        entity_id = entity.id
        conditions = scope.conditions()
        if query:
            pattern = f"%{_escape_like(query)}%"
            conditions.append(
                or_(*(field.ilike(pattern, escape="\\") for field in searched))
            )
        cost = func.coalesce(func.sum(LLMUsageDB.cost_usd), 0)
        stmt = (
            select(entity_id.label("key"), label.label("label"), cost.label("cost_usd"))
            .select_from(LLMUsageDB)
            .join(entity, entity_id == column)
            .where(*conditions)
            .group_by(entity_id, label)
            .order_by(cost.desc(), label)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.all())

    async def labels(
        self, dimension: UsageDimension, ids: Sequence[UUID]
    ) -> dict[UUID, str]:
        """Display names for the ids of an entity dimension that still exist."""
        if not ids:
            return {}
        if dimension is UsageDimension.user:
            stmt = select(UserDB.id, UserDB.name, UserDB.email).where(
                UserDB.id.in_(ids)
            )
            result = await self.db.execute(stmt)
            return {row.id: row.name or row.email or "Unnamed user" for row in result}
        model = {
            UsageDimension.agent: AgentDB,
            UsageDimension.project: ProjectDB,
            UsageDimension.trigger: TriggerDB,
            UsageDimension.workspace: WorkspaceDB,
            UsageDimension.mcp: MCPServerDB,
            UsageDimension.skill: SkillDB,
        }.get(dimension)
        if model is None:
            return {}
        stmt = select(model.id, model.name).where(model.id.in_(ids))
        result = await self.db.execute(stmt)
        return {row.id: row.name for row in result}


class UsageSettingsRepository(BaseRepository[UsageSettingsDB]):
    def __init__(self, db: AsyncSession):
        super().__init__(UsageSettingsDB, db)

    async def get_for_workspace(self, workspace_id: UUID) -> UsageSettingsDB | None:
        stmt = select(UsageSettingsDB).where(
            UsageSettingsDB.workspace_id == workspace_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def save(
        self,
        workspace_id: UUID,
        *,
        currency: str,
        usd_rate: Decimal,
        monthly_budget: Decimal | None,
    ) -> UsageSettingsDB:
        row = await self.get_for_workspace(workspace_id)
        if row is None:
            try:
                async with self.db.begin_nested():
                    row = UsageSettingsDB(
                        workspace_id=workspace_id,
                        currency=currency,
                        usd_rate=usd_rate,
                        monthly_budget=monthly_budget,
                    )
                    self.db.add(row)
                    await self.db.flush()
                return row
            except IntegrityError:
                row = await self.get_for_workspace(workspace_id)
                if row is None:
                    raise
        row.currency = currency
        row.usd_rate = usd_rate
        row.monthly_budget = monthly_budget
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row


class UsageLedgerStateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self) -> UsageLedgerStateDB | None:
        return await self.db.get(UsageLedgerStateDB, 1)

    async def mark_backfill_completed(self) -> None:
        stmt = (
            update(UsageLedgerStateDB)
            .where(UsageLedgerStateDB.id == 1)
            .values(backfill_completed_at=datetime.now(UTC))
        )
        await self.db.execute(stmt)

    async def mark_tool_shares_backfill_completed(self) -> None:
        stmt = (
            update(UsageLedgerStateDB)
            .where(col(UsageLedgerStateDB.id) == 1)
            .values(tool_shares_backfill_completed_at=datetime.now(UTC))
        )
        await self.db.execute(stmt)
