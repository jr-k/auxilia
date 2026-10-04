import logging
from uuid import UUID

from app.database import AsyncSessionLocal
from app.exceptions import DomainError
from app.integrations.channels.service import ChannelService
from app.integrations.discord.client import DiscordClient
from app.integrations.discord.consumer import build_discord_delivery
from app.notifications.models import ExternalProvider


logger = logging.getLogger(__name__)
EPHEMERAL = 64


def interaction_user(payload: dict) -> dict:
    member = payload.get("member")
    if isinstance(member, dict) and isinstance(member.get("user"), dict):
        return member["user"]
    user = payload.get("user")
    return user if isinstance(user, dict) else {}


def subcommand(payload: dict) -> tuple[str, dict[str, object]]:
    options = (payload.get("data") or {}).get("options") or []
    if not options or not isinstance(options[0], dict):
        return "", {}
    command = options[0]
    values = {
        str(option.get("name")): option.get("value")
        for option in command.get("options") or []
        if isinstance(option, dict)
    }
    return str(command.get("name") or ""), values


def _scope(payload: dict, external_user_id: str) -> str:
    return str(payload.get("channel_id") or f"dm:{external_user_id}")


def _display_name(user: dict) -> str | None:
    return (
        str(user.get("global_name") or "").strip()
        or str(user.get("username") or "").strip()
        or None
    )


async def handle_link(payload: dict, workspace_id: UUID) -> dict:
    user = interaction_user(payload)
    external_user_id = str(user.get("id") or "")
    _, values = subcommand(payload)
    code = str(values.get("code") or "")
    try:
        async with AsyncSessionLocal() as db:
            await ChannelService(db).consume_link_code(
                workspace_id=workspace_id,
                provider=ExternalProvider.discord,
                external_user_id=external_user_id,
                display_name=_display_name(user),
                code=code,
            )
            await db.commit()
        content = "Account linked. Use `/auxilia new` to choose an agent."
    except DomainError as exc:
        content = str(exc)
    return {"type": 4, "data": {"content": content, "flags": EPHEMERAL}}


async def handle_new(payload: dict, workspace_id: UUID) -> dict:
    user = interaction_user(payload)
    external_user_id = str(user.get("id") or "")
    _, values = subcommand(payload)
    try:
        agent_id = UUID(str(values.get("agent") or ""))
        async with AsyncSessionLocal() as db:
            service = ChannelService(db)
            identity = await service.identities.get_external(
                workspace_id, ExternalProvider.discord, external_user_id
            )
            if identity is None:
                return _link_required()
            await service.select_agent(
                workspace_id=workspace_id,
                identity=identity,
                provider=ExternalProvider.discord,
                external_chat_id=_scope(payload, external_user_id),
                agent_id=agent_id,
            )
            await db.commit()
        content = "Agent selected. Use `/auxilia ask` to send a message."
    except (DomainError, ValueError) as exc:
        content = str(exc)
    return {"type": 4, "data": {"content": content, "flags": EPHEMERAL}}


async def handle_autocomplete(payload: dict, workspace_id: UUID) -> dict:
    user = interaction_user(payload)
    external_user_id = str(user.get("id") or "")
    _, values = subcommand(payload)
    query = str(values.get("agent") or "").lower()
    async with AsyncSessionLocal() as db:
        service = ChannelService(db)
        identity = await service.identities.get_external(
            workspace_id, ExternalProvider.discord, external_user_id
        )
        agents = await service.list_agents(workspace_id, identity) if identity else []
    choices = [
        {
            "name": f"{agent.emoji or ''} {agent.name}".strip()[:100],
            "value": str(agent.id),
        }
        for agent in agents
        if not query or query in (agent.name or "").lower()
    ][:25]
    return {"type": 8, "data": {"choices": choices}}


async def process_ask(payload: dict, workspace_id: UUID, bot_token: str) -> None:
    user = interaction_user(payload)
    external_user_id = str(user.get("id") or "")
    _, values = subcommand(payload)
    prompt = str(values.get("prompt") or "").strip()
    application_id = str(payload.get("application_id") or "")
    interaction_token = str(payload.get("token") or "")
    channel_id = str(payload.get("channel_id") or "")
    client = DiscordClient(bot_token)
    message_id: str | None = None
    try:
        if not channel_id:
            raise ValueError("Discord interaction has no channel")
        async with AsyncSessionLocal() as db:
            service = ChannelService(db)
            identity = await service.identities.get_external(
                workspace_id, ExternalProvider.discord, external_user_id
            )
            if identity is None:
                await client.edit_original(
                    application_id,
                    interaction_token,
                    "Link your account first with `/auxilia link`.",
                )
                return
            conversation = await service.conversations.get_scope(
                workspace_id,
                ExternalProvider.discord,
                _scope(payload, external_user_id),
                "",
                external_user_id,
            )
            if conversation is None:
                await client.edit_original(
                    application_id,
                    interaction_token,
                    "Choose an agent first with `/auxilia new`.",
                )
                return
            placeholder = await client.send_channel_message(channel_id, "Queued…")
            message_id = str(placeholder["id"])
            await service.enqueue_message(
                conversation=conversation,
                identity=identity,
                text=prompt,
                delivery=build_discord_delivery(
                    workspace_id=workspace_id,
                    channel_id=channel_id,
                    message_id=message_id,
                    external_user_id=external_user_id,
                ),
            )
        await client.edit_original(
            application_id,
            interaction_token,
            "Run queued. The response will appear in this channel.",
        )
    except Exception:
        logger.exception("Discord ask failed")
        if message_id is not None:
            await client.edit_channel_message(
                channel_id, message_id, "Could not start the run."
            )
        await client.edit_original(
            application_id, interaction_token, "Could not start the run."
        )


async def process_hitl(payload: dict, workspace_id: UUID, bot_token: str) -> None:
    user = interaction_user(payload)
    external_user_id = str(user.get("id") or "")
    custom_id = str((payload.get("data") or {}).get("custom_id") or "")
    application_id = str(payload.get("application_id") or "")
    interaction_token = str(payload.get("token") or "")
    channel_id = str(payload.get("channel_id") or "")
    client = DiscordClient(bot_token)
    message_id: str | None = None
    try:
        if not channel_id:
            raise ValueError("Discord interaction has no channel")
        _, token, decision = custom_id.split(":", 2)
        async with AsyncSessionLocal() as db:
            service = ChannelService(db)
            identity = await service.identities.get_external(
                workspace_id, ExternalProvider.discord, external_user_id
            )
            if identity is None:
                await client.edit_original(
                    application_id, interaction_token, "Link your account first."
                )
                return
            placeholder = await client.send_channel_message(
                channel_id, "Saving decision…"
            )
            message_id = str(placeholder["id"])
            resumed = await service.decide_action(
                ExternalProvider.discord,
                token,
                decision,
                build_discord_delivery(
                    workspace_id=workspace_id,
                    channel_id=channel_id,
                    message_id=message_id,
                    external_user_id=external_user_id,
                ),
                identity.user_id,
            )
        if not resumed and message_id is not None:
            await client.edit_channel_message(
                channel_id,
                message_id,
                "Decision saved. Waiting for the remaining approvals.",
            )
        await client.edit_original(
            application_id,
            interaction_token,
            "Decision saved. Resuming…" if resumed else "Decision saved.",
        )
    except Exception:
        logger.exception("Discord approval failed")
        if message_id is not None:
            await client.edit_channel_message(
                channel_id, message_id, "Could not resume the run."
            )
        await client.edit_original(
            application_id,
            interaction_token,
            "This approval is no longer valid.",
        )


def _link_required() -> dict:
    return {
        "type": 4,
        "data": {
            "content": "Link your auxilia account first with `/auxilia link code:…`.",
            "flags": EPHEMERAL,
        },
    }
