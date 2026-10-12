import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.realtime.models import WorkspaceEventOutboxDB
from app.redis_client import get_redis


_KIND = "kind"
_TARGET_USER_ID = "target_user_id"
_THREAD_ID = "thread_id"
_PAYLOAD = "payload"
_EVENT_KEY = "event_key"
_MAX_EVENTS = 10_000
_TTL_SECONDS = 24 * 60 * 60


def workspace_events_key(workspace_id: UUID) -> str:
    return f"workspace:{workspace_id}:events"


@dataclass(frozen=True)
class WorkspaceEvent:
    id: str
    event_key: str
    kind: str
    target_user_id: str | None
    thread_id: str | None
    payload: dict | None

    def sse(self) -> str:
        data: dict[str, Any] = {"kind": self.kind, "eventKey": self.event_key}
        if self.thread_id is not None:
            data["threadId"] = self.thread_id
        if self.payload is not None:
            data["payload"] = self.payload
        return (
            f"id: {self.id}\n"
            "event: invalidate\n"
            f"data: {json.dumps(data, separators=(',', ':'))}\n\n"
        )


class WorkspaceEventStream:
    def __init__(self, workspace_id: UUID, redis: Redis | None = None):
        self.redis = redis or get_redis()
        self._key = workspace_events_key(workspace_id)

    async def publish(self, row: WorkspaceEventOutboxDB) -> str:
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.xadd(
                self._key,
                {
                    _KIND: row.kind,
                    _TARGET_USER_ID: (
                        str(row.target_user_id)
                        if row.target_user_id is not None
                        else ""
                    ),
                    _THREAD_ID: row.thread_id or "",
                    _EVENT_KEY: str(row.id),
                    _PAYLOAD: (
                        json.dumps(row.payload, separators=(",", ":"))
                        if row.payload is not None
                        else ""
                    ),
                },
                maxlen=_MAX_EVENTS,
                approximate=True,
            )
            pipe.expire(self._key, _TTL_SECONDS)
            event_id, _ = await pipe.execute()
        return event_id

    async def latest_id(self) -> str:
        entries = await self.redis.xrevrange(self._key, count=1)
        return entries[0][0] if entries else "0-0"

    async def read_batch(
        self,
        cursor: str,
        *,
        block_ms: int = 15_000,
    ) -> tuple[str, list[WorkspaceEvent]] | None:
        result = await self.redis.xread(
            {self._key: cursor},
            block=block_ms,
            count=100,
        )
        if not result:
            return None
        _, entries = result[0]
        events: list[WorkspaceEvent] = []
        for event_id, fields in entries:
            cursor = event_id
            events.append(
                WorkspaceEvent(
                    id=event_id,
                    event_key=fields.get(_EVENT_KEY) or event_id,
                    kind=fields[_KIND],
                    target_user_id=fields.get(_TARGET_USER_ID) or None,
                    thread_id=fields.get(_THREAD_ID) or None,
                    payload=(
                        json.loads(fields[_PAYLOAD]) if fields.get(_PAYLOAD) else None
                    ),
                )
            )
        return cursor, events
