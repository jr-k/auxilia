from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.whatsapp.outbound import WhatsAppOutboundGateway
from app.integrations.whatsapp.repository import (
    AgentWhatsAppConnectionRepository,
    WhatsAppIdentityRepository,
    WhatsAppThreadBindingRepository,
)
from app.integrations.whatsapp.service import WhatsAppConnectionService


logger = logging.getLogger(__name__)
_MESSAGE_CHUNK_CHARS = 4_096
_MAX_MESSAGE_CHARS = 16_384


@dataclass(frozen=True)
class WhatsAppRunTools:
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


def _bound_whatsapp_tools(
    db: AsyncSession,
    gateway: WhatsAppOutboundGateway,
    *,
    display_phone_number: str | None,
) -> tuple[BaseTool, ...]:
    @tool
    async def whatsapp_send_message(text: str) -> str:
        """Send a message to the current user's linked WhatsApp account.

        Use only when the user explicitly asks to send, post, or forward
        content to WhatsApp. The destination is fixed by their linked Auxilia
        profile. WhatsApp permits this only during the 24-hour service window.
        """
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text cannot be empty")
        if len(cleaned_text) > _MAX_MESSAGE_CHARS:
            raise ValueError(f"text cannot exceed {_MAX_MESSAGE_CHARS} characters")
        message_ids = [
            await gateway.send_text(chunk) for chunk in _message_chunks(cleaned_text)
        ]
        await db.commit()
        return json.dumps(
            {
                "ok": True,
                "display_phone_number": display_phone_number,
                "message_ids": message_ids,
                "message_count": len(message_ids),
            },
            ensure_ascii=False,
        )

    return (whatsapp_send_message,)


async def build_whatsapp_run_tools(
    db: AsyncSession,
    delivery: dict[str, Any] | None,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
) -> WhatsAppRunTools:
    identity = await WhatsAppIdentityRepository(db).get_for_user(workspace_id, user_id)
    if identity is None:
        return WhatsAppRunTools()
    rows = await AgentWhatsAppConnectionRepository(db).list_for_agent(
        workspace_id, agent_id
    )
    service = WhatsAppConnectionService(db)
    active = []
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
        return WhatsAppRunTools()
    selected = active[0]
    if isinstance(delivery, dict) and delivery.get("channel") == "whatsapp":
        try:
            delivery_connection_id = UUID(str(delivery.get("whatsapp_connection_id")))
        except ValueError:
            logger.warning("WhatsApp delivery has an invalid whatsapp_connection_id")
        else:
            selected = next(
                (config for config in active if config.id == delivery_connection_id),
                selected,
            )
    else:
        binding = await WhatsAppThreadBindingRepository(db).get_private_for_identity(
            [config.id for config in active], identity.whatsapp_user_id
        )
        if binding is not None:
            selected = next(
                (
                    config
                    for config in active
                    if config.id == binding.whatsapp_connection_id
                ),
                selected,
            )
    gateway = WhatsAppOutboundGateway(
        db,
        selected,
        recipient_id=identity.whatsapp_user_id,
    )
    tools = _bound_whatsapp_tools(
        db,
        gateway,
        display_phone_number=selected.display_phone_number,
    )
    return WhatsAppRunTools(tools=tools, interrupt_on={})
