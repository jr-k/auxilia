from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal
from app.exceptions import (
    DomainValidationError,
    InvalidCredentialsError,
    PermissionDeniedError,
)
from app.notifications.service import NotificationChannelService
from app.threads.models import ThreadDB
from app.triggers.models import TriggerType
from app.triggers.schemas import TriggerCreate
from app.triggers.service import TriggerService
from app.users.models import UserDB, WorkspaceRole
from app.visibility import ResourceVisibility
from app.workspaces.repository import WorkspaceRepository


NOTIFICATION_SYSTEM_PROMPT = """Auxilia provides built-in notification tools.
When the user explicitly asks to be notified, reminded, alerted, or to receive a
recurring briefing, use these built-in tools by default. If the user explicitly
names another notification service or an MCP integration, use that requested
service instead. Do not claim a notification was created unless the tool call
succeeds."""


class NotifyUserInput(BaseModel):
    title: str = Field(max_length=150)
    body: str = Field(max_length=10_000)
    channel_names: list[str] | None = Field(
        default=None,
        description=(
            "Exact configured channel names. Omit to use all enabled default channels."
        ),
    )


class ListNotificationChannelsInput(BaseModel):
    pass


class ScheduleUserNotificationInput(BaseModel):
    name: str = Field(
        max_length=255,
        description="Short label shown in the user's automation list.",
    )
    instructions: str = Field(
        max_length=110_000,
        description=(
            "What this agent must determine or summarize on every occurrence. "
            "Do not include delivery instructions."
        ),
    )
    cron_expression: str = Field(
        max_length=255,
        description="Standard five-field cron expression.",
    )
    timezone: str = Field(
        max_length=64,
        description=(
            "IANA timezone for the schedule, for example Europe/Paris. "
            "Ask the user when it cannot be determined safely."
        ),
    )
    channel_names: list[str] | None = Field(
        default=None,
        description=(
            "Exact configured channel names. Omit to follow the user's enabled "
            "default channels dynamically."
        ),
    )


async def _load_user(db, thread: ThreadDB) -> UserDB:
    user = await db.get(UserDB, thread.user_id)
    if user is None:
        raise InvalidCredentialsError("Notification owner no longer exists")
    membership = await WorkspaceRepository(db).get_membership(
        thread.workspace_id, user.id
    )
    if membership is None:
        raise InvalidCredentialsError(
            "Notification owner no longer belongs to this workspace"
        )
    user.set_workspace_membership(membership)
    return user


def _available_tool_name(name: str, reserved_names: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in reserved_names:
        candidate = f"{name}_{suffix}"
        suffix += 1
    reserved_names.add(candidate)
    return candidate


def build_notification_tools(
    thread: ThreadDB,
    *,
    reserved_names: set[str] | None = None,
) -> list[BaseTool]:
    used_names = set(reserved_names or ())

    async def list_notification_channels() -> list[dict]:
        """List the caller's configured Auxilia notification destinations."""
        async with AsyncSessionLocal() as db:
            channels = await NotificationChannelService(
                db, thread.workspace_id
            ).list_channels(thread.user_id)
        return [
            {
                "name": channel.name,
                "technology": channel.channel_type.value,
                "enabled": channel.enabled,
                "default": channel.is_default,
            }
            for channel in channels
        ]

    async def notify_user(
        title: str,
        body: str,
        channel_names: list[str] | None = None,
    ) -> dict:
        """Send one notification now through the user's configured channels."""
        async with AsyncSessionLocal() as db:
            result = await NotificationChannelService(db, thread.workspace_id).send(
                user_id=thread.user_id,
                title=title,
                body=body,
                agent_id=thread.agent_id,
                url=f"/agents/{thread.agent_id}/chat/{thread.id}",
                channel_names=channel_names,
            )
        return result.model_dump(mode="json")

    async def schedule_user_notification(
        name: str,
        instructions: str,
        cron_expression: str,
        timezone: str,
        channel_names: list[str] | None = None,
    ) -> dict:
        """Schedule this agent and deliver every result as a notification."""
        if thread.model_id is None:
            raise DomainValidationError(
                "This conversation has no model selected for scheduled runs"
            )
        async with AsyncSessionLocal() as db:
            user = await _load_user(db, thread)
            if user.role is WorkspaceRole.member:
                raise PermissionDeniedError(
                    "Editor access is required to schedule notifications"
                )
            channels = NotificationChannelService(db, thread.workspace_id)
            channel_ids = await channels.select_for_schedule(user.id, channel_names)
            trigger = await TriggerService(db, thread.workspace_id).create(
                TriggerCreate(
                    name=name,
                    instructions=instructions,
                    agent_id=thread.agent_id,
                    model_id=thread.model_id,
                    reasoning_effort=thread.reasoning_effort,
                    trigger_type=TriggerType.schedule,
                    cron_expression=cron_expression,
                    timezone=timezone,
                    visibility=ResourceVisibility.personal,
                ),
                owner=user,
            )
            await channels.bind_trigger(trigger.id, channel_ids)
            await db.commit()
        return {
            "trigger_id": str(trigger.id),
            "name": trigger.name,
            "next_run_at": (
                trigger.next_run_at.isoformat() if trigger.next_run_at else None
            ),
            "timezone": trigger.timezone,
            "channels": channel_names or "defaults",
        }

    return [
        StructuredTool.from_function(
            coroutine=list_notification_channels,
            name=_available_tool_name("list_notification_channels", used_names),
            description=(
                "List the current user's configured Auxilia notification channels, "
                "including their exact names, technology, enabled state, and default "
                "state. Use this before selecting a named channel. It is unnecessary "
                "when the user did not specify a destination because defaults apply."
            ),
            args_schema=ListNotificationChannelsInput,
        ),
        StructuredTool.from_function(
            coroutine=notify_user,
            name=_available_tool_name("notify_user", used_names),
            description=(
                "Send an immediate notification through Auxilia's configured "
                "notification channels. Use when the user explicitly asks to be "
                "notified now. Omit channel_names to use their defaults. If they "
                "explicitly request another notification MCP, use that MCP instead."
            ),
            args_schema=NotifyUserInput,
        ),
        StructuredTool.from_function(
            coroutine=schedule_user_notification,
            name=_available_tool_name("schedule_user_notification", used_names),
            description=(
                "Create a recurring notification powered by the current agent. "
                "Use when the user asks to be notified, reminded, or briefed on a "
                "schedule. Convert the requested schedule to five-field cron and "
                "supply an IANA timezone. Omit channel_names to follow the user's "
                "default channels. Use another MCP only when explicitly requested."
            ),
            args_schema=ScheduleUserNotificationInput,
        ),
    ]
