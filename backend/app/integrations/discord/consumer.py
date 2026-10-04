import logging
import time
from typing import Any, Final, Literal, TypedDict, cast
from uuid import UUID

from redis.asyncio import Redis

from app.auth.settings import auth_settings
from app.database import AsyncSessionLocal, get_checkpointer
from app.integrations.channels.protocol import ChannelProtocolAdapter
from app.integrations.channels.service import ChannelService
from app.integrations.discord.client import DiscordClient
from app.notifications.models import ExternalProvider
from app.notifications.service import DiscordNotificationSettingsService
from app.runtime.checkpoints import checkpoint_thread_id
from app.runtime.hitl import load_interrupt_scope, pending_approval_requests
from app.runtime.protocol.wire import decode_event
from app.runtime.runs.delivery import DeliveryConsumer
from app.runtime.runs.models import RunDB
from app.runtime.runs.service import RunService
from app.runtime.runs.state import RunStatus, is_terminal
from app.threads.repository import ThreadRepository


logger = logging.getLogger(__name__)
DISCORD_CHANNEL: Final = "discord"
DISCORD_TEXT_CHUNK: Final = 1900


class DiscordDelivery(TypedDict):
    channel: Literal["discord"]
    workspace_id: str
    channel_id: str
    message_id: str
    external_user_id: str


def build_discord_delivery(
    *,
    workspace_id: UUID,
    channel_id: str,
    message_id: str,
    external_user_id: str,
) -> DiscordDelivery:
    return {
        "channel": DISCORD_CHANNEL,
        "workspace_id": str(workspace_id),
        "channel_id": channel_id,
        "message_id": message_id,
        "external_user_id": external_user_id,
    }


def build_discord_run_consumer(record: RunDB) -> "DiscordRunConsumer | None":
    delivery = record.delivery
    if not delivery or delivery.get("channel") != DISCORD_CHANNEL:
        return None
    if delivery.get("workspace_id") != str(record.workspace_id):
        logger.error("Discord delivery workspace mismatch for run %s", record.id)
        return None
    return DiscordRunConsumer(record)


class DiscordRunConsumer(DeliveryConsumer):
    def __init__(self, record: RunDB, redis: Redis | None = None):
        self.record = record
        self.delivery = cast(DiscordDelivery, record.delivery or {})
        self.redis = redis

    async def _client(self) -> DiscordClient | None:
        async with AsyncSessionLocal() as db:
            config = await DiscordNotificationSettingsService(db).get_runtime_config(
                self.record.workspace_id
            )
        return DiscordClient(config.bot_token) if config else None

    async def run(self) -> None:
        client = await self._client()
        if client is None:
            logger.warning("Discord delivery skipped for run %s", self.record.id)
            return
        channel_id = self.delivery["channel_id"]
        message_id = self.delivery["message_id"]
        try:
            await client.edit_channel_message(channel_id, message_id, "Thinking…")
            text = await self._stream(client, message_id)
            status = await self._terminal_status()
            final = text.strip() or "Done."
            await client.edit_channel_message(
                channel_id, message_id, final[:DISCORD_TEXT_CHUNK]
            )
            for offset in range(DISCORD_TEXT_CHUNK, len(final), DISCORD_TEXT_CHUNK):
                await client.send_channel_message(
                    channel_id,
                    final[offset : offset + DISCORD_TEXT_CHUNK],
                )
            if status is RunStatus.interrupted:
                await self._post_approvals(client)
            elif status is RunStatus.success:
                await self._post_auxilia_link(client)
            elif status in {RunStatus.error, RunStatus.timeout}:
                await client.send_channel_message(
                    channel_id,
                    "Sorry — the run failed. Please try again.",
                )
        except Exception:
            logger.exception("Discord delivery crashed for run %s", self.record.id)

    async def _stream(self, client: DiscordClient, message_id: str) -> str:
        adapter = ChannelProtocolAdapter()
        text = ""
        last_edit = time.monotonic()
        last_sent = ""
        async for raw in RunService(self.redis).stream(self.record.id):
            event = decode_event(raw)
            if event is None:
                continue
            if _is_failed_terminal(event):
                error = (event["params"]["data"] or {}).get("error")
                text += f"\n\nError: {error or 'Unknown error'}"
            else:
                text += "".join(adapter.texts(event))
            now = time.monotonic()
            visible = text.strip()[:DISCORD_TEXT_CHUNK]
            if visible and visible != last_sent and now - last_edit >= 0.8:
                await client.edit_channel_message(
                    self.delivery["channel_id"],
                    message_id,
                    visible,
                )
                last_sent = visible
                last_edit = now
        return text

    async def _terminal_status(self) -> RunStatus | None:
        record = await RunService(self.redis).get(self.record.id)
        return record.status if is_terminal(record.status) else None

    async def _post_approvals(self, client: DiscordClient) -> None:
        async with get_checkpointer() as checkpointer:
            scope = await load_interrupt_scope(
                checkpointer,
                checkpoint_thread_id(self.record.workspace_id, self.record.thread_id),
            )
        if scope is None:
            return
        requests = pending_approval_requests(
            scope.root, scope.state, interrupt_id=scope.interrupt.id
        )
        interrupt_id = scope.interrupt.id or "legacy"
        async with AsyncSessionLocal() as db:
            rows = await ChannelService(db).create_actions(
                provider=ExternalProvider.discord,
                workspace_id=self.record.workspace_id,
                user_id=self.record.user_id,
                thread_id=self.record.thread_id,
                interrupt_id=interrupt_id,
                requests=requests,
            )
            await db.commit()
        for request, row in zip(requests, rows, strict=True):
            await client.send_channel_message(
                self.delivery["channel_id"],
                f"Approve **{request['tool_name']}**?\n"
                f"```json\n{request.get('input') or {}}\n```",
                components=[
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "style": 3,
                                "label": "Approve",
                                "custom_id": f"hitl:{row.token}:approve",
                            },
                            {
                                "type": 2,
                                "style": 4,
                                "label": "Reject",
                                "custom_id": f"hitl:{row.token}:reject",
                            },
                        ],
                    }
                ],
            )

    async def _post_auxilia_link(self, client: DiscordClient) -> None:
        async with AsyncSessionLocal() as db:
            thread = await ThreadRepository(db, self.record.workspace_id).get(
                self.record.thread_id
            )
        if thread is None:
            return
        await client.send_channel_message(
            self.delivery["channel_id"],
            f"View in auxilia: {auth_settings.FRONTEND_URL}/agents/"
            f"{thread.agent_id}/chat/{thread.id}",
        )


def _is_failed_terminal(event: dict[str, Any]) -> bool:
    params = event.get("params") or {}
    data = params.get("data")
    return (
        event.get("method") == "lifecycle"
        and not params.get("namespace")
        and isinstance(data, dict)
        and data.get("event") == "failed"
    )
