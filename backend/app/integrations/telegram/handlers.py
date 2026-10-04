import logging
from uuid import UUID

from app.database import AsyncSessionLocal
from app.exceptions import DomainError
from app.integrations.channels.service import ChannelService
from app.integrations.telegram.client import TelegramClient
from app.integrations.telegram.consumer import build_telegram_delivery
from app.notifications.models import ExternalProvider


logger = logging.getLogger(__name__)


def _display_name(user: dict) -> str | None:
    parts = [
        str(user.get("first_name") or "").strip(),
        str(user.get("last_name") or "").strip(),
    ]
    name = " ".join(part for part in parts if part)
    return name or str(user.get("username") or "").strip() or None


async def handle_update(
    update: dict, *, workspace_id: UUID, client: TelegramClient
) -> None:
    if isinstance(update.get("callback_query"), dict):
        await _handle_callback(
            update["callback_query"], workspace_id=workspace_id, client=client
        )
        return
    message = update.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("from"), dict):
        return
    await _handle_message(message, workspace_id=workspace_id, client=client)


async def _handle_message(
    message: dict, *, workspace_id: UUID, client: TelegramClient
) -> None:
    sender = message["from"]
    external_user_id = str(sender.get("id") or "")
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    topic = str(message.get("message_thread_id") or "")
    text = str(message.get("text") or "").strip()
    if not external_user_id or not chat_id or not text:
        return
    async with AsyncSessionLocal() as db:
        service = ChannelService(db)
        if text.lower().startswith("/link "):
            if chat.get("type") != "private":
                await client.send_message(
                    chat_id,
                    "For security, link your account in a private chat with this bot.",
                    message_thread_id=topic,
                )
                return
            code = text.split(maxsplit=1)[1]
            try:
                await service.consume_link_code(
                    workspace_id=workspace_id,
                    provider=ExternalProvider.telegram,
                    external_user_id=external_user_id,
                    display_name=_display_name(sender),
                    code=code,
                )
                await db.commit()
                await client.send_message(
                    chat_id,
                    "Account linked. Use /new to choose an agent.",
                    message_thread_id=topic,
                )
            except DomainError as exc:
                await client.send_message(chat_id, str(exc), message_thread_id=topic)
            return
        identity = await service.identities.get_external(
            workspace_id, ExternalProvider.telegram, external_user_id
        )
        if identity is None:
            await client.send_message(
                chat_id,
                "Link your auxilia account first with /link CODE. "
                "Generate the code in Settings → Connected accounts.",
                message_thread_id=topic,
            )
            return
        if text.lower() in {"/start", "/new"}:
            agents = await service.list_agents(workspace_id, identity)
            if not agents:
                await client.send_message(
                    chat_id,
                    "No agent is available to your account.",
                    message_thread_id=topic,
                )
                return
            keyboard = [
                [
                    {
                        "text": f"{agent.emoji or ''} {agent.name}".strip(),
                        "callback_data": f"agent:{agent.id}",
                    }
                ]
                for agent in agents[:50]
            ]
            await client.send_message(
                chat_id,
                "Choose an agent:",
                message_thread_id=topic,
                reply_markup={"inline_keyboard": keyboard},
            )
            return
        conversation = await service.conversations.get_scope(
            workspace_id,
            ExternalProvider.telegram,
            chat_id,
            topic,
            external_user_id,
        )
        if conversation is None:
            await client.send_message(
                chat_id,
                "Use /new to choose an agent before sending a message.",
                message_thread_id=topic,
            )
            return
        delivery = build_telegram_delivery(
            workspace_id=workspace_id,
            chat_id=chat_id,
            message_thread_id=topic,
            external_user_id=external_user_id,
        )
        try:
            await service.enqueue_message(
                conversation=conversation,
                identity=identity,
                text=text,
                delivery=delivery,
            )
        except DomainError as exc:
            await client.send_message(chat_id, str(exc), message_thread_id=topic)


async def _handle_callback(
    callback: dict, *, workspace_id: UUID, client: TelegramClient
) -> None:
    callback_id = str(callback.get("id") or "")
    sender = callback.get("from") or {}
    external_user_id = str(sender.get("id") or "")
    message = callback.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id") or "")
    topic = str(message.get("message_thread_id") or "")
    data = str(callback.get("data") or "")
    if not callback_id or not external_user_id or not chat_id:
        return
    async with AsyncSessionLocal() as db:
        service = ChannelService(db)
        identity = await service.identities.get_external(
            workspace_id, ExternalProvider.telegram, external_user_id
        )
        if identity is None:
            await client.answer_callback(callback_id, "Link your auxilia account first")
            return
        try:
            if data.startswith("agent:"):
                agent_id = UUID(data.removeprefix("agent:"))
                await service.select_agent(
                    workspace_id=workspace_id,
                    identity=identity,
                    provider=ExternalProvider.telegram,
                    external_chat_id=chat_id,
                    external_thread_id=topic,
                    agent_id=agent_id,
                )
                await db.commit()
                await client.answer_callback(callback_id, "Agent selected")
                await client.send_message(
                    chat_id,
                    "Agent selected. Send a message to begin.",
                    message_thread_id=topic,
                )
                return
            if data.startswith("hitl:"):
                _, token, decision = data.split(":", 2)
                delivery = build_telegram_delivery(
                    workspace_id=workspace_id,
                    chat_id=chat_id,
                    message_thread_id=topic,
                    external_user_id=external_user_id,
                )
                resumed = await service.decide_action(
                    ExternalProvider.telegram,
                    token,
                    decision,
                    delivery,
                    identity.user_id,
                )
                await client.answer_callback(
                    callback_id,
                    "Decision saved; resuming…" if resumed else "Decision saved",
                )
                return
        except (DomainError, ValueError):
            logger.exception("Telegram callback failed")
            await client.answer_callback(callback_id, "This action is no longer valid")
            return
    await client.answer_callback(callback_id)
