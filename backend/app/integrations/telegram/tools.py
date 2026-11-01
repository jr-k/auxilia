"""Run-scoped Telegram tools backed by the user's linked profile identity.

The bot token and destination stay inside the worker process. Neither is
exposed in a tool schema, result, checkpoint, or prompt.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.telegram.client import TelegramClient
from app.integrations.telegram.repository import (
    AgentTelegramBotRepository,
    TelegramIdentityRepository,
    TelegramThreadBindingRepository,
)
from app.integrations.telegram.service import TelegramBotService


logger = logging.getLogger(__name__)

_MESSAGE_CHUNK_CHARS = 4_096
_MAX_MESSAGE_CHARS = 16_384


@dataclass(frozen=True)
class TelegramRunTools:
    """Tools injected when this user can receive messages from the agent bot."""

    tools: tuple[BaseTool, ...] = ()
    interrupt_on: dict[str, bool] | None = None


def _message_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= _MESSAGE_CHUNK_CHARS:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, _MESSAGE_CHUNK_CHARS + 1)
        if split_at < _MESSAGE_CHUNK_CHARS // 2:
            split_at = _MESSAGE_CHUNK_CHARS
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    return chunks


def _bound_telegram_tools(
    client: TelegramClient,
    *,
    chat_id: str,
    bot_username: str | None,
) -> tuple[BaseTool, ...]:
    @tool
    async def telegram_send_message(text: str) -> str:
        """Send a message to the current user's linked Telegram account.

        Use only when the user explicitly asks to send, post, or forward
        content to their Telegram conversation. The destination is fixed from
        their linked Auxilia profile and cannot be changed by tool arguments.
        """
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text cannot be empty")
        if len(cleaned_text) > _MAX_MESSAGE_CHARS:
            raise ValueError(f"text cannot exceed {_MAX_MESSAGE_CHARS} characters")

        sent = [
            await client.send_message(chat_id, chunk)
            for chunk in _message_chunks(cleaned_text)
        ]
        return json.dumps(
            {
                "ok": True,
                "bot_username": bot_username,
                "message_ids": [
                    message.get("message_id")
                    for message in sent
                    if isinstance(message.get("message_id"), int)
                ],
                "message_count": len(sent),
            },
            ensure_ascii=False,
        )

    return (telegram_send_message,)


async def build_telegram_run_tools(
    db: AsyncSession,
    delivery: dict[str, Any] | None,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
) -> TelegramRunTools:
    """Resolve a profile-bound Telegram sender for this run's user and agent."""
    identity = await TelegramIdentityRepository(db).get_for_user(workspace_id, user_id)
    if identity is None:
        return TelegramRunTools()

    rows = await AgentTelegramBotRepository(db).list_for_agent(workspace_id, agent_id)
    active = []
    service = TelegramBotService(db)
    for row in rows:
        config = await service.get_runtime(row.id)
        if (
            config is not None
            and config.workspace_id == workspace_id
            and config.agent_id == agent_id
            and config.workspace_enabled
            and config.enabled
        ):
            active.append(config)
    if not active:
        return TelegramRunTools()

    selected = active[0]
    selected_from_delivery = False
    if isinstance(delivery, dict) and delivery.get("channel") == "telegram":
        raw_bot_id = delivery.get("telegram_bot_id")
        try:
            delivery_bot_id = UUID(str(raw_bot_id))
        except ValueError:
            logger.warning("Telegram delivery has an invalid telegram_bot_id")
        else:
            matching = next(
                (config for config in active if config.id == delivery_bot_id),
                None,
            )
            if matching is not None:
                selected = matching
                selected_from_delivery = True
    if not selected_from_delivery:
        binding = await TelegramThreadBindingRepository(db).get_private_for_identity(
            [config.id for config in active],
            identity.telegram_user_id,
        )
        if binding is not None:
            selected = next(
                (config for config in active if config.id == binding.telegram_bot_id),
                selected,
            )

    tools = _bound_telegram_tools(
        TelegramClient(selected.bot_token),
        chat_id=identity.telegram_user_id,
        bot_username=selected.bot_username,
    )
    # The current prompt must explicitly ask for the send. The destination is
    # fixed to the authenticated user's linked identity, so no second approval
    # is needed and no arbitrary Telegram recipient can be supplied.
    return TelegramRunTools(tools=tools, interrupt_on={})
