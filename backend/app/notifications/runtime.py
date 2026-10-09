import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SlackRuntimeConfig:
    workspace_id: UUID
    slack_team_id: str
    bot_token: str
    signing_secret: str


_CACHE_TTL_SECONDS = 30.0
_cache: tuple[float, tuple[SlackRuntimeConfig, ...]] | None = None
_cache_lock = asyncio.Lock()


def invalidate_slack_runtime_cache() -> None:
    global _cache
    _cache = None


async def get_cached_slack_runtime_configs(
    load: Callable[[], Awaitable[tuple[SlackRuntimeConfig, ...]]],
) -> tuple[SlackRuntimeConfig, ...]:
    global _cache

    now = time.monotonic()
    if _cache is not None and now < _cache[0]:
        return _cache[1]
    async with _cache_lock:
        now = time.monotonic()
        if _cache is not None and now < _cache[0]:
            return _cache[1]
        configs = await load()
        _cache = (now + _CACHE_TTL_SECONDS, configs)
        return configs
