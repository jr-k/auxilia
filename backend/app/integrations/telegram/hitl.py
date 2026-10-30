from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.service import AgentService
from app.agents.models import EffectivePermission
from app.database import get_checkpointer
from app.exceptions import DomainValidationError, NotFoundError
from app.integrations.telegram.client import TelegramClient
from app.integrations.telegram.db_models import TelegramIdentityDB
from app.integrations.telegram.repository import TelegramApprovalRepository
from app.integrations.telegram.service import TelegramRuntimeConfig
from app.runtime.checkpoints import checkpoint_thread_id
from app.runtime.hitl import load_interrupt_scope, pending_approval_requests
from app.runtime.runs.service import RunService
from app.threads.repository import ThreadRepository
from app.workspaces.repository import WorkspaceRepository


async def _clear_buttons(
    client: TelegramClient,
    chat_id: str,
    rows: list,
) -> None:
    for row in rows:
        if row.message_id is not None:
            await client.edit_reply_markup(
                chat_id, row.message_id, {"inline_keyboard": []}
            )


async def handle_approval_callback(
    db: AsyncSession,
    *,
    callback: dict[str, Any],
    config: TelegramRuntimeConfig,
    identity: TelegramIdentityDB,
    client: TelegramClient,
) -> None:
    callback_id = str(callback.get("id") or "")
    data = str(callback.get("data") or "")
    message = callback.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id") or "")
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "th":
        raise DomainValidationError("Invalid approval action")
    token, shorthand = parts[1:]
    decision = {"a": "approve", "r": "reject"}.get(shorthand)
    if decision is None:
        raise DomainValidationError("Invalid approval decision")
    repository = TelegramApprovalRepository(db)
    initial = await repository.get_token(token)
    if (
        initial is None
        or initial.user_id != identity.user_id
        or initial.workspace_id != config.workspace_id
        or initial.telegram_bot_id != config.id
    ):
        raise NotFoundError("Approval request not found")
    thread = await ThreadRepository(db, config.workspace_id).get(initial.thread_id)
    membership = await WorkspaceRepository(db).get_membership(
        config.workspace_id, identity.user_id
    )
    if thread is None or membership is None:
        raise NotFoundError("Approval request not found")
    await AgentService(db, config.workspace_id).require_permission(
        thread.agent_id,
        user_id=identity.user_id,
        user_role=membership.role,
        user_team_id=membership.team_id,
        at_least=EffectivePermission.member,
        action="approve tools for this agent",
    )
    batch = await repository.list_interrupt(
        initial.thread_id, initial.interrupt_id, for_update=True
    )
    action = next((row for row in batch if row.token == token), None)
    if action is None:
        raise NotFoundError("Approval request not found")
    if action.decision is not None:
        await client.answer_callback(callback_id, "This decision was already saved")
        return
    async with get_checkpointer() as checkpointer:
        scope = await load_interrupt_scope(
            checkpointer,
            checkpoint_thread_id(config.workspace_id, initial.thread_id),
        )
    if scope is None or scope.interrupt.id != initial.interrupt_id:
        for row in batch:
            if row.decision is None:
                row.decision = "stale"
                db.add(row)
        await db.commit()
        await _clear_buttons(client, chat_id, batch)
        await client.answer_callback(callback_id, "Already handled elsewhere")
        return
    requests = pending_approval_requests(
        scope.root, scope.state, interrupt_id=scope.interrupt.id
    )
    request_ids = [request["tool_call_id"] for request in requests]
    if set(request_ids) != {row.tool_call_id for row in batch}:
        for row in batch:
            if row.decision is None:
                row.decision = "stale"
                db.add(row)
        await db.commit()
        await _clear_buttons(client, chat_id, batch)
        await client.answer_callback(callback_id, "Already handled elsewhere")
        return
    action.decision = decision
    db.add(action)
    await db.flush()
    if any(row.decision is None for row in batch):
        await db.commit()
        await client.edit_reply_markup(
            chat_id,
            int(message["message_id"]),
            {"inline_keyboard": []},
        )
        await client.answer_callback(callback_id, "Decision saved")
        return
    by_tool = {row.tool_call_id: row for row in batch}
    command = {
        "resume": {
            "interrupt_id": initial.interrupt_id,
            "decisions": [
                {
                    "tool_call_id": tool_call_id,
                    "type": by_tool[tool_call_id].decision,
                }
                for tool_call_id in request_ids
            ],
        }
    }
    delivery = {
        "channel": "telegram",
        "workspace_id": str(config.workspace_id),
        "telegram_bot_id": str(config.id),
        "chat_id": chat_id,
        "message_thread_id": str(message.get("message_thread_id") or ""),
        "telegram_user_id": identity.telegram_user_id,
        "show_tool_callouts": config.show_tool_callouts,
        "force_enable_all_capabilities": (
            config.tool_discovery_mode.force_enable_all_capabilities
        ),
        "tool_discovery_mode": config.tool_discovery_mode.runtime_mode.value,
    }
    await RunService().create_in_session(
        db,
        thread_id=initial.thread_id,
        user_id=str(identity.user_id),
        command=command,
        delivery=delivery,
        multitask_strategy="enqueue",
    )
    await db.commit()
    await _clear_buttons(client, chat_id, batch)
    await client.answer_callback(callback_id, "Decisions saved. Resuming.")
