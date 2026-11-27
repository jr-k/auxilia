"""One-shot imports of usage that predates the ledger, read back from checkpoints.

Runs once per deployment history, on a dispatcher instance, behind an advisory
lock. Two phases, each marked done in `llm_usage_state`:

- the ledger itself, for threads created before live recording started;
- the MCP server and skill shares of ledger rows recorded before shares were.

Rows dedupe on (thread_id, message_id) and shares on (usage_id, dimension,
key) against what the recorder wrote, so an interrupted import simply starts
over on the next boot. Prices are the catalog's current ones, as for the
per-conversation estimate; owners of tool calls are the workspace's current
servers and skills. History only covers what checkpoints retained: deleted
threads, and tool-discovery router calls (never checkpointed), are absent.
"""

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from uuid import UUID

from langchain_core.messages import AIMessage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, engine
from app.model_providers.whitelist import SupportedModel
from app.runtime.api.costs import decode_message_write
from app.runtime.api.protocol_repository import CheckpointWriteRepository
from app.runtime.checkpoints import checkpoint_thread_id
from app.threads.models import ThreadDB
from app.usage.models import UsageLedgerStateDB
from app.usage.recorder import (
    UsageAttribution,
    load_catalog,
    load_tool_owners,
    usage_row,
)
from app.usage.repository import UsageLedgerStateRepository, UsageRepository
from app.usage.tools import ToolOwners, tool_shares


logger = logging.getLogger(__name__)

THREAD_BATCH = 200
INSERT_BATCH = 500
# Yield between threads so the import never starves live requests.
THREAD_PAUSE_SECONDS = 0.02
LOCK_SQL = "hashtext('auxilia.llm_usage_backfill')"


def _message_key(message: AIMessage) -> str:
    return message.id or (
        "sha256:" + hashlib.sha256(message.model_dump_json().encode()).hexdigest()
    )


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def _thread_messages(
    db: AsyncSession, thread: ThreadDB
) -> dict[str, tuple[datetime, AIMessage]]:
    """Every AI message of the thread's checkpoints by key, dated by its first write."""
    earliest: dict[str, tuple[datetime, AIMessage]] = {}
    writes = CheckpointWriteRepository(db).iter_timed_message_writes(
        checkpoint_thread_id(thread.workspace_id, thread.id)
    )
    async for type_tag, blob, ts in writes:
        occurred_at = _parse_ts(ts) or thread.created_at
        for message in await asyncio.to_thread(decode_message_write, type_tag, blob):
            # A message recurs in later writes (compaction rewrites the
            # list): date it by its first write, and keep a copy that still
            # carries usage.
            key = _message_key(message)
            seen = earliest.get(key)
            if seen is None:
                earliest[key] = (occurred_at, message)
                continue
            kept = (
                message
                if message.usage_metadata and not seen[1].usage_metadata
                else seen[1]
            )
            earliest[key] = (min(seen[0], occurred_at), kept)
    return earliest


class UsageBackfill:
    def __init__(self) -> None:
        self._owners: dict[UUID, ToolOwners] = {}

    async def run(self) -> None:
        try:
            async with engine.connect() as lock:
                acquired = await lock.scalar(
                    text(f"SELECT pg_try_advisory_lock({LOCK_SQL})")
                )
                await lock.commit()
                if not acquired:
                    return
                try:
                    await self._run()
                finally:
                    await lock.execute(text(f"SELECT pg_advisory_unlock({LOCK_SQL})"))
                    await lock.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "LLM usage history import failed; it will retry on restart"
            )

    async def _run(self) -> None:
        async with AsyncSessionLocal() as db:
            state = await UsageLedgerStateRepository(db).get()
        if state is None:
            return
        if state.backfill_completed_at is None:
            await self._import_usage(state)
        if state.tool_shares_backfill_completed_at is None:
            await self._import_tool_shares(state)

    async def _import_usage(self, state: UsageLedgerStateDB) -> None:
        logger.info("Importing LLM usage history from checkpoints")
        catalog = await load_catalog()
        imported = await self._each_thread(
            state.tracking_started_at,
            lambda thread: self._thread_usage(thread, catalog),
        )
        async with AsyncSessionLocal() as db:
            await UsageLedgerStateRepository(db).mark_backfill_completed()
            await db.commit()
        logger.info("LLM usage history imported: %d calls", imported)

    async def _import_tool_shares(self, state: UsageLedgerStateDB) -> None:
        logger.info("Importing MCP server and skill shares of LLM usage")
        imported = await self._each_thread(
            state.tool_shares_started_at, self._thread_tool_shares
        )
        async with AsyncSessionLocal() as db:
            await UsageLedgerStateRepository(db).mark_tool_shares_backfill_completed()
            await db.commit()
        logger.info("LLM usage tool shares imported: %d shares", imported)

    async def _each_thread(
        self, cutoff: datetime, work: Callable[[ThreadDB], Awaitable[int]]
    ) -> int:
        imported = 0
        async for thread in self._threads(cutoff):
            try:
                imported += await work(thread)
            except Exception:  # noqa: BLE001 — one bad thread must not stop the import
                logger.warning(
                    "Could not import usage history of thread %s",
                    thread.id,
                    exc_info=True,
                )
        return imported

    async def _threads(self, cutoff: datetime) -> AsyncIterator[ThreadDB]:
        cursor: tuple[datetime, str] | None = None
        while True:
            async with AsyncSessionLocal() as db:
                threads = await UsageRepository(db).threads_created_before(
                    cutoff, cursor, THREAD_BATCH
                )
            if not threads:
                return
            for thread in threads:
                yield thread
                await asyncio.sleep(THREAD_PAUSE_SECONDS)
            last = threads[-1]
            cursor = (last.created_at, last.id)

    async def _tool_owners(self, db: AsyncSession, workspace_id: UUID) -> ToolOwners:
        owners = self._owners.get(workspace_id)
        if owners is None:
            owners = await load_tool_owners(db, workspace_id)
            self._owners[workspace_id] = owners
        return owners

    async def _thread_usage(
        self, thread: ThreadDB, catalog: dict[str, SupportedModel]
    ) -> int:
        async with AsyncSessionLocal() as db:
            attribution = await UsageAttribution.for_thread(
                db, thread, await self._tool_owners(db, thread.workspace_id)
            )
            rows = []
            for key, (occurred_at, message) in (
                await _thread_messages(db, thread)
            ).items():
                row = usage_row(message, attribution, catalog, occurred_at)
                if row is not None:
                    rows.append({**row, "message_id": key})
            repository = UsageRepository(db)
            for start in range(0, len(rows), INSERT_BATCH):
                await repository.insert_many(rows[start : start + INSERT_BATCH])
            await db.commit()
        return len(rows)

    async def _thread_tool_shares(self, thread: ThreadDB) -> int:
        async with AsyncSessionLocal() as db:
            repository = UsageRepository(db)
            usage_ids = await repository.usage_ids_by_message(thread.id)
            if not usage_ids:
                return 0
            owners = await self._tool_owners(db, thread.workspace_id)
            rows = [
                {"usage_id": usage_ids[key], **share}
                for key, (_, message) in (await _thread_messages(db, thread)).items()
                if key in usage_ids
                for share in tool_shares(message, owners)
            ]
            for start in range(0, len(rows), INSERT_BATCH):
                await repository.insert_tool_shares(rows[start : start + INSERT_BATCH])
            await db.commit()
        return len(rows)
