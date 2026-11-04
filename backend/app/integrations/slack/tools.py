"""Run-scoped Slack tools backed by an agent-specific Slack installation.

The bot token stays inside the worker process and is captured only by the tool
closures. It is never exposed in a tool schema, result, checkpoint, or prompt.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from redis.exceptions import RedisError
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_async_handlers import (
    AsyncRateLimitErrorRetryHandler,
)
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.slack.service import (
    AgentSlackBotService,
    AgentSlackRuntimeConfig,
)
from app.redis_client import get_redis


logger = logging.getLogger(__name__)

_CHANNEL_ID = re.compile(r"^[CG][A-Z0-9]+$")
_MESSAGE_TS = re.compile(r"^\d+\.\d+$")
_MAX_SCANNED_MESSAGES = 1_000
_MAX_RESULT_TEXT_CHARS = 1_500
_CHANNEL_MATCH_THRESHOLD = 0.72
_CHANNEL_MATCH_MARGIN = 0.08
_CHANNEL_CACHE_TTL_SECONDS = 300
_CHANNEL_CACHE_PREFIX = "slack:channel-index:"


@dataclass(frozen=True)
class SlackTarget:
    """One active agent bot that may deliver a direct Slack action."""

    client: AsyncWebClient
    team_id: str
    bot_id: UUID


@dataclass(frozen=True)
class SlackChannel:
    """One named Slack channel visible to an active agent bot."""

    target: SlackTarget
    channel_id: str
    name: str


@dataclass(frozen=True)
class SlackRunTools:
    """Direct Slack tools available to interactive and autonomous runs."""

    tools: tuple[BaseTool, ...] = ()
    interrupt_on: dict[str, bool] | None = None


def _channel_name(value: str) -> str:
    cleaned = value.strip().removeprefix("#").strip()
    if not cleaned or len(cleaned) > 80:
        raise ValueError("channel must be a Slack channel name or ID")
    return cleaned


def _normalized_channel_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _channel_match_score(requested: str, candidate: str) -> float:
    if requested == candidate:
        return 1.0
    score = SequenceMatcher(None, requested, candidate).ratio()
    if requested in candidate or candidate in requested:
        overlap = min(len(requested), len(candidate)) / max(
            len(requested), len(candidate)
        )
        score = max(score, 0.75 + 0.2 * overlap)
    requested_parts = set(requested.split("-"))
    candidate_parts = set(candidate.split("-"))
    union = requested_parts | candidate_parts
    intersection = requested_parts & candidate_parts
    if intersection and union:
        token_overlap = len(intersection) / len(union)
        score = max(score, 0.75 + 0.2 * token_overlap)
    return score


def _thread_ts(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not _MESSAGE_TS.fullmatch(cleaned):
        raise ValueError("thread_ts must be a Slack message timestamp")
    return cleaned


def _message_summary(message: dict[str, Any]) -> dict[str, Any] | None:
    ts = message.get("ts")
    text = message.get("text")
    if not isinstance(ts, str) or not isinstance(text, str):
        return None
    return {
        "ts": ts,
        "thread_ts": message.get("thread_ts") or ts,
        "user": message.get("user"),
        "bot_id": message.get("bot_id"),
        "text": text[:_MAX_RESULT_TEXT_CHARS],
        "reply_count": message.get("reply_count", 0),
    }


async def _readable_channel(
    targets: Sequence[SlackTarget],
    channel_id: str,
) -> SlackTarget | None:
    for target in targets:
        try:
            await target.client.conversations_history(channel=channel_id, limit=1)
        except SlackApiError:
            continue
        return target
    return None


def _channel_cache_key(target: SlackTarget) -> str:
    return f"{_CHANNEL_CACHE_PREFIX}{target.bot_id}"


async def _cached_channels(target: SlackTarget) -> list[SlackChannel] | None:
    try:
        raw = await get_redis().get(_channel_cache_key(target))
    except RedisError:
        logger.warning("Could not read Slack channel cache", exc_info=True)
        return None
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, list):
        return None
    channels: list[SlackChannel] = []
    for item in decoded:
        if not isinstance(item, dict):
            continue
        channel_id = item.get("id")
        name = item.get("name")
        if isinstance(channel_id, str) and isinstance(name, str):
            channels.append(SlackChannel(target, channel_id, name))
    return channels


async def _list_target_channels(
    target: SlackTarget,
    *,
    refresh: bool = False,
) -> list[SlackChannel]:
    if not refresh:
        cached = await _cached_channels(target)
        if cached is not None:
            return cached

    channels: list[SlackChannel] = []
    cursor: str | None = None
    while True:
        response = await target.client.conversations_list(
            types="public_channel,private_channel",
            exclude_archived=True,
            limit=200,
            cursor=cursor,
        )
        raw_channels = response.get("channels")
        page_channels = raw_channels if isinstance(raw_channels, list) else []
        for item in page_channels:
            if not isinstance(item, dict) or item.get("is_member") is False:
                continue
            channel_id = item.get("id")
            name = item.get("name")
            if isinstance(channel_id, str) and isinstance(name, str):
                channels.append(SlackChannel(target, channel_id, name))

        metadata = response.get("response_metadata")
        next_cursor = (
            metadata.get("next_cursor") if isinstance(metadata, dict) else None
        )
        cursor = (
            next_cursor
            if isinstance(next_cursor, str) and next_cursor.strip()
            else None
        )
        if cursor is None:
            break

    payload = json.dumps(
        [{"id": item.channel_id, "name": item.name} for item in channels],
        ensure_ascii=False,
    )
    try:
        await get_redis().set(
            _channel_cache_key(target),
            payload,
            ex=_CHANNEL_CACHE_TTL_SECONDS,
        )
    except RedisError:
        logger.warning("Could not update Slack channel cache", exc_info=True)
    return channels


async def _available_channels(
    targets: Sequence[SlackTarget],
    *,
    refresh: bool = False,
) -> list[SlackChannel]:
    channels: list[SlackChannel] = []
    for target in targets:
        channels.extend(await _list_target_channels(target, refresh=refresh))
    return channels


async def _resolve_channel(
    targets: Sequence[SlackTarget],
    channel: str,
    *,
    require_read: bool,
) -> SlackChannel:
    requested = _channel_name(channel)
    possible_id = requested.upper()
    if _CHANNEL_ID.fullmatch(possible_id):
        target = (
            await _readable_channel(targets, possible_id)
            if require_read or len(targets) > 1
            else targets[0]
        )
        if target is None:
            raise ValueError(
                "No connected Slack bot can access the requested channel ID"
            )
        return SlackChannel(target, possible_id, possible_id)

    available_channels = await _available_channels(targets)

    normalized_requested = _normalized_channel_name(requested)

    def rank(channels: Sequence[SlackChannel]) -> list[tuple[float, SlackChannel]]:
        return sorted(
            (
                (
                    _channel_match_score(
                        normalized_requested,
                        _normalized_channel_name(candidate.name),
                    ),
                    candidate,
                )
                for candidate in channels
            ),
            key=lambda item: item[0],
            reverse=True,
        )

    ranked = rank(available_channels)
    if not ranked or ranked[0][0] < _CHANNEL_MATCH_THRESHOLD:
        available_channels = await _available_channels(targets, refresh=True)
        ranked = rank(available_channels)
    suggestions = ", ".join(f"#{candidate.name}" for _, candidate in ranked[:5])
    if not ranked or ranked[0][0] < _CHANNEL_MATCH_THRESHOLD:
        detail = f" Closest channels: {suggestions}." if suggestions else ""
        raise ValueError(
            f"No connected Slack channel confidently matches #{requested}.{detail}"
        )
    best_score, best = ranked[0]
    if len(ranked) > 1 and best_score - ranked[1][0] < _CHANNEL_MATCH_MARGIN:
        raise ValueError(
            f"Several Slack channels could match #{requested}: {suggestions}. "
            "Use a more specific name or the channel ID."
        )
    if (
        require_read
        and await _readable_channel((best.target,), best.channel_id) is None
    ):
        raise ValueError(
            f"The Slack bot cannot read the best match, #{best.name}. "
            "Check that the bot belongs to the channel."
        )
    return best


def _bound_slack_tools(targets: Sequence[SlackTarget]) -> tuple[BaseTool, ...]:
    @tool
    async def slack_search_channel_messages(
        channel: str,
        query: str,
        limit: int = 20,
    ) -> str:
        """Search recent messages in a channel this agent's Slack bot can read.

        `channel` accepts an exact or approximate channel name, such as
        `transfo`, `transfo ia`, or `#transfo-ia`, as well as a C... or G...
        channel ID. The tool lists accessible channels and picks a name only
        when the match is unambiguous. Use this before replying when the user
        identifies a message by text rather than by Slack timestamp. Returns
        JSON containing each matching message's `ts` and reply-ready `thread_ts`.
        """
        resolved = await _resolve_channel(targets, channel, require_read=True)
        needle = query.strip().casefold()
        if not 2 <= len(needle) <= 300:
            raise ValueError("query must contain between 2 and 300 characters")
        bounded_limit = max(1, min(limit, 50))
        matches: list[dict[str, Any]] = []
        scanned = 0
        cursor: str | None = None

        while scanned < _MAX_SCANNED_MESSAGES and len(matches) < bounded_limit:
            response = await resolved.target.client.conversations_history(
                channel=resolved.channel_id,
                cursor=cursor,
                limit=min(200, _MAX_SCANNED_MESSAGES - scanned),
            )
            page = response.get("messages")
            messages = page if isinstance(page, list) else []
            scanned += len(messages)
            for raw in messages:
                if not isinstance(raw, dict):
                    continue
                text = raw.get("text")
                if not isinstance(text, str) or needle not in text.casefold():
                    continue
                summary = _message_summary(raw)
                if summary is not None:
                    matches.append(summary)
                if len(matches) >= bounded_limit:
                    break

            metadata = response.get("response_metadata")
            next_cursor = (
                metadata.get("next_cursor") if isinstance(metadata, dict) else None
            )
            cursor = (
                next_cursor
                if isinstance(next_cursor, str) and next_cursor.strip()
                else None
            )
            if cursor is None or not messages:
                break

        return json.dumps(
            {
                "channel_id": resolved.channel_id,
                "channel_name": resolved.name,
                "slack_team_id": resolved.target.team_id,
                "query": query.strip(),
                "scanned": scanned,
                "matches": matches,
            },
            ensure_ascii=False,
        )

    @tool
    async def slack_post_message(
        channel: str,
        text: str,
        thread_ts: str | None = None,
        reply_broadcast: bool = False,
    ) -> str:
        """Post a Slack message as this agent's dedicated Slack bot.

        This is the primary tool for any explicit request to send, post,
        publish, share, or forward content on Slack, including requests made
        from web chat and scheduled runs. Use it directly instead of a browser,
        computer-control tool, or external Slack MCP. `channel` accepts an exact
        or approximate name. The tool lists accessible channels and publishes
        only when one match is clearly better than the alternatives. To reply
        below an existing message, pass the `thread_ts` returned by
        `slack_search_channel_messages`.
        """
        resolved = await _resolve_channel(targets, channel, require_read=False)
        resolved_thread = _thread_ts(thread_ts)
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text cannot be empty")
        if len(cleaned_text) > 4_000:
            raise ValueError("text cannot exceed 4000 characters")

        kwargs: dict[str, Any] = {
            "channel": resolved.channel_id,
            "text": cleaned_text,
            "unfurl_links": False,
            "unfurl_media": False,
        }
        if resolved_thread is not None:
            kwargs["thread_ts"] = resolved_thread
            kwargs["reply_broadcast"] = reply_broadcast
        response = await resolved.target.client.chat_postMessage(**kwargs)
        return json.dumps(
            {
                "ok": bool(response.get("ok", True)),
                "channel": response.get("channel", resolved.channel_id),
                "channel_name": resolved.name,
                "slack_team_id": resolved.target.team_id,
                "ts": response.get("ts"),
                "thread_ts": resolved_thread,
            },
            ensure_ascii=False,
        )

    return slack_search_channel_messages, slack_post_message


def _target(config: AgentSlackRuntimeConfig) -> SlackTarget:
    client = AsyncWebClient(token=config.bot_token)
    client.retry_handlers.append(AsyncRateLimitErrorRetryHandler(max_retry_count=1))
    return SlackTarget(
        client=client,
        team_id=config.slack_team_id,
        bot_id=config.id,
    )


async def build_slack_run_tools(
    db: AsyncSession,
    delivery: dict[str, Any] | None,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,  # noqa: ARG001 - shared runtime-tool factory interface
) -> SlackRunTools:
    """Resolve active agent Slack bots without exposing their tokens."""
    service = AgentSlackBotService(db, workspace_id)
    configs = [
        config
        for config in await service.list_for_verification(agent_id)
        if config.enabled
        and config.workspace_enabled
        and config.workspace_id == workspace_id
        and config.agent_id == agent_id
    ]

    if isinstance(delivery, dict) and delivery.get("channel") == "slack":
        raw_bot_id = delivery.get("slack_bot_id")
        try:
            slack_bot_id = UUID(str(raw_bot_id))
        except ValueError:
            logger.warning("Slack delivery has an invalid slack_bot_id")
            return SlackRunTools()
        configs = [config for config in configs if config.id == slack_bot_id]
        if not configs:
            logger.warning("Slack run tools skipped because the bot is inactive")
            return SlackRunTools()
    if not configs:
        return SlackRunTools()

    tools = _bound_slack_tools(tuple(_target(config) for config in configs))
    # The current request is already the user's authorization. The write tool's
    # description requires an explicit send/publish request, while Slack scopes
    # and channel membership remain the final authorization boundary.
    return SlackRunTools(tools=tools, interrupt_on={})
