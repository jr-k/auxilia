"""Run-scoped Slack tools backed by an agent-specific Slack installation.

The bot token stays inside the worker process and is captured only by the tool
closures. It is never exposed in a tool schema, result, checkpoint, or prompt.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.slack.service import AgentSlackBotService


logger = logging.getLogger(__name__)

_CHANNEL_ID = re.compile(r"^[CG][A-Z0-9]+$")
_MESSAGE_TS = re.compile(r"^\d+\.\d+$")
_MAX_SCANNED_MESSAGES = 1_000
_MAX_RESULT_TEXT_CHARS = 1_500


@dataclass(frozen=True)
class SlackRunTools:
    """Tools injected only into a run delivered through an agent Slack bot."""

    tools: tuple[BaseTool, ...] = ()
    interrupt_on: dict[str, bool] | None = None


def _channel_id(value: str) -> str:
    cleaned = value.strip().upper()
    if not _CHANNEL_ID.fullmatch(cleaned):
        raise ValueError("channel_id must be a Slack public/private channel ID")
    return cleaned


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


def _bound_slack_tools(client: AsyncWebClient) -> tuple[BaseTool, ...]:
    @tool
    async def slack_search_channel_messages(
        channel_id: str,
        query: str,
        limit: int = 20,
    ) -> str:
        """Search recent messages in a channel this agent's Slack bot can read.

        Use this before replying when the user identifies a message by text
        rather than by Slack timestamp. `channel_id` must be a C... or G...
        channel ID. Matching is case-insensitive substring matching. Returns
        JSON containing each matching message's `ts` and reply-ready `thread_ts`.
        """
        resolved_channel = _channel_id(channel_id)
        needle = query.strip().casefold()
        if not 2 <= len(needle) <= 300:
            raise ValueError("query must contain between 2 and 300 characters")
        bounded_limit = max(1, min(limit, 50))
        matches: list[dict[str, Any]] = []
        scanned = 0
        cursor: str | None = None

        while scanned < _MAX_SCANNED_MESSAGES and len(matches) < bounded_limit:
            response = await client.conversations_history(
                channel=resolved_channel,
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
                "channel_id": resolved_channel,
                "query": query.strip(),
                "scanned": scanned,
                "matches": matches,
            },
            ensure_ascii=False,
        )

    @tool
    async def slack_post_message(
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
        reply_broadcast: bool = False,
    ) -> str:
        """Post a Slack message as this agent's dedicated Slack bot.

        Use only when the current user explicitly asks to send or publish a
        Slack message. To reply below an existing message, pass the `thread_ts`
        returned by `slack_search_channel_messages`. Slack still enforces
        channel membership and the bot installation's scopes.
        """
        resolved_channel = _channel_id(channel_id)
        resolved_thread = _thread_ts(thread_ts)
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text cannot be empty")
        if len(cleaned_text) > 4_000:
            raise ValueError("text cannot exceed 4000 characters")

        # Keep writes limited to conversations this installation can already
        # read, even if it was granted Slack's broader chat:write.public scope.
        await client.conversations_history(channel=resolved_channel, limit=1)
        kwargs: dict[str, Any] = {
            "channel": resolved_channel,
            "text": cleaned_text,
            "unfurl_links": False,
            "unfurl_media": False,
        }
        if resolved_thread is not None:
            kwargs["thread_ts"] = resolved_thread
            kwargs["reply_broadcast"] = reply_broadcast
        response = await client.chat_postMessage(**kwargs)
        return json.dumps(
            {
                "ok": bool(response.get("ok", True)),
                "channel": response.get("channel", resolved_channel),
                "ts": response.get("ts"),
                "thread_ts": resolved_thread,
            },
            ensure_ascii=False,
        )

    return slack_search_channel_messages, slack_post_message


async def build_slack_run_tools(
    db: AsyncSession,
    delivery: dict[str, Any] | None,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,  # noqa: ARG001 - shared runtime-tool factory interface
) -> SlackRunTools:
    """Resolve tools for a Slack-bound run without exposing the bot token."""
    if not isinstance(delivery, dict) or delivery.get("channel") != "slack":
        return SlackRunTools()
    raw_bot_id = delivery.get("slack_bot_id")
    if not isinstance(raw_bot_id, str):
        return SlackRunTools()
    try:
        slack_bot_id = UUID(raw_bot_id)
    except ValueError:
        logger.warning("Slack delivery has an invalid slack_bot_id")
        return SlackRunTools()

    config = await AgentSlackBotService(db).get_runtime(slack_bot_id)
    if config is None:
        logger.warning("Slack run tools skipped because the bot is inactive")
        return SlackRunTools()
    if config.workspace_id != workspace_id or config.agent_id != agent_id:
        logger.error("Slack run tool installation does not match the run agent")
        return SlackRunTools()

    tools = _bound_slack_tools(AsyncWebClient(token=config.bot_token))
    # The current request is already the user's authorization. The write tool's
    # description requires an explicit send/publish request, while Slack scopes
    # and channel membership remain the final authorization boundary.
    return SlackRunTools(tools=tools, interrupt_on={})
