from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.service import AgentService
from app.agents.models import EffectivePermission
from app.database import get_checkpointer
from app.exceptions import DomainValidationError, NotFoundError
from app.integrations.whatsapp.db_models import WhatsAppIdentityDB
from app.integrations.whatsapp.outbound import WhatsAppOutboundGateway
from app.integrations.whatsapp.repository import WhatsAppApprovalRepository
from app.integrations.whatsapp.service import WhatsAppRuntimeConfig
from app.runtime.checkpoints import checkpoint_thread_id
from app.runtime.hitl import load_interrupt_scope, pending_approval_requests
from app.runtime.runs.service import RunService
from app.threads.repository import ThreadRepository
from app.workspaces.repository import WorkspaceRepository


async def handle_approval_reply(
    db: AsyncSession,
    *,
    action_id: str,
    config: WhatsAppRuntimeConfig,
    identity: WhatsAppIdentityDB,
    chat_id: str,
    recipient_type: str,
) -> None:
    parts = action_id.split(":")
    if len(parts) != 3 or parts[0] != "th":
        raise DomainValidationError("Invalid approval action")
    token, decision = parts[1:]
    if decision not in {"approve", "reject"}:
        raise DomainValidationError("Invalid approval decision")
    repository = WhatsAppApprovalRepository(db)
    initial = await repository.get_token(token)
    if (
        initial is None
        or initial.user_id != identity.user_id
        or initial.workspace_id != config.workspace_id
        or initial.whatsapp_connection_id != config.id
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
    gateway = WhatsAppOutboundGateway(
        db,
        config,
        recipient_id=chat_id,
        recipient_type=recipient_type,
    )
    if action.decision is not None:
        await gateway.send_text("This decision was already saved.")
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
        await gateway.send_text("This approval was already handled elsewhere.")
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
        await gateway.send_text("This approval was already handled elsewhere.")
        return
    action.decision = decision
    db.add(action)
    await db.flush()
    if any(row.decision is None for row in batch):
        await db.commit()
        await gateway.send_text("Decision saved.")
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
        "channel": "whatsapp",
        "workspace_id": str(config.workspace_id),
        "whatsapp_connection_id": str(config.id),
        "recipient_id": chat_id,
        "recipient_type": recipient_type,
        "whatsapp_user_id": identity.whatsapp_user_id,
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
    await gateway.send_text("Decisions saved. Resuming.")
