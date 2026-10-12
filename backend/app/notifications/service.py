import logging
from uuid import UUID

from fastapi import Depends
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.settings import auth_settings
from app.database import get_db
from app.exceptions import AlreadyExistsError, DomainValidationError, NotFoundError
from app.integrations.slack.service import AgentSlackBotService
from app.notifications.models import (
    NotificationChannelDB,
    NotificationChannelType,
    TriggerNotificationDB,
)
from app.notifications.repository import (
    NotificationChannelRepository,
    SlackNotificationSettingsRepository,
    TriggerNotificationRepository,
)
from app.notifications.runtime import (
    SlackRuntimeConfig,
    invalidate_slack_runtime_cache,
)
from app.notifications.schemas import (
    NotificationChannelCreate,
    NotificationChannelPatch,
    NotificationChannelResponse,
    NotificationChannelTestResponse,
    SlackNotificationSettingsResponse,
    SlackNotificationSettingsUpdate,
)
from app.realtime.schemas import WorkspaceEventKind
from app.realtime.service import stage_workspace_event
from app.workspaces.dependencies import get_active_workspace_id


logger = logging.getLogger(__name__)


class NotificationChannelService:
    def __init__(self, db: AsyncSession, workspace_id: UUID):
        self.db = db
        self.workspace_id = workspace_id
        self.repository = NotificationChannelRepository(db)
        self.trigger_notifications = TriggerNotificationRepository(db)

    @staticmethod
    def _response(channel: NotificationChannelDB) -> NotificationChannelResponse:
        return NotificationChannelResponse.model_validate(channel)

    async def list_channels(self, user_id: UUID) -> list[NotificationChannelResponse]:
        return [
            self._response(channel)
            for channel in await self.repository.list_for_user(
                self.workspace_id, user_id
            )
        ]

    @staticmethod
    def _normalized_config(channel_type: NotificationChannelType, config: dict) -> dict:
        if channel_type is NotificationChannelType.browser:
            if config:
                raise DomainValidationError(
                    "Browser notification channels do not accept configuration"
                )
            return {}
        channel_id = config.get("channel_id")
        if not isinstance(channel_id, str) or not channel_id.strip():
            raise DomainValidationError(
                "Slack notification channels require a channel_id"
            )
        if len(channel_id.strip()) > 255:
            raise DomainValidationError("Slack channel_id is too long")
        if set(config) != {"channel_id"}:
            raise DomainValidationError(
                "Slack notification config only accepts channel_id"
            )
        return {"channel_id": channel_id.strip()}

    async def create(
        self, data: NotificationChannelCreate, user_id: UUID
    ) -> NotificationChannelResponse:
        name = data.name.strip()
        if not name:
            raise DomainValidationError("Notification channel name cannot be empty")
        if (
            await self.repository.get_by_name(self.workspace_id, user_id, name)
            is not None
        ):
            raise AlreadyExistsError(
                f"A notification channel named '{name}' already exists"
            )
        if data.channel_type is NotificationChannelType.browser and (
            await self.repository.get_by_type(
                self.workspace_id, user_id, NotificationChannelType.browser
            )
            is not None
        ):
            raise AlreadyExistsError(
                "A browser notification channel is already configured"
            )
        channel = NotificationChannelDB(
            workspace_id=self.workspace_id,
            user_id=user_id,
            name=name,
            channel_type=data.channel_type,
            enabled=data.enabled,
            is_default=data.is_default,
            config=self._normalized_config(data.channel_type, data.config),
        )
        try:
            self.db.add(channel)
            await self.db.flush()
            await self.db.refresh(channel)
        except IntegrityError as exc:
            raise AlreadyExistsError(
                f"A notification channel named '{name}' already exists"
            ) from exc
        return self._response(channel)

    async def update(
        self,
        channel_id: UUID,
        data: NotificationChannelPatch,
        user_id: UUID,
    ) -> NotificationChannelResponse:
        channel = await self.repository.get_for_user(
            channel_id, self.workspace_id, user_id
        )
        if channel is None:
            raise NotFoundError("Notification channel not found")
        values = data.model_dump(exclude_unset=True)
        null_fields = [
            field
            for field in ("name", "enabled", "is_default", "config")
            if field in values and values[field] is None
        ]
        if null_fields:
            raise DomainValidationError(
                f"Notification channel fields cannot be null: {', '.join(null_fields)}"
            )
        if "name" in values:
            name = values["name"].strip()
            if not name:
                raise DomainValidationError("Notification channel name cannot be empty")
            existing = await self.repository.get_by_name(
                self.workspace_id, user_id, name
            )
            if existing is not None and existing.id != channel.id:
                raise AlreadyExistsError(
                    f"A notification channel named '{name}' already exists"
                )
            channel.name = name
        if "config" in values:
            channel.config = self._normalized_config(
                channel.channel_type, values["config"]
            )
        if "enabled" in values:
            channel.enabled = values["enabled"]
        if "is_default" in values:
            channel.is_default = values["is_default"]
        try:
            self.db.add(channel)
            await self.db.flush()
            await self.db.refresh(channel)
        except IntegrityError as exc:
            raise AlreadyExistsError(
                f"A notification channel named '{channel.name}' already exists"
            ) from exc
        return self._response(channel)

    async def delete(self, channel_id: UUID, user_id: UUID) -> None:
        channel = await self.repository.get_for_user(
            channel_id, self.workspace_id, user_id
        )
        if channel is None:
            raise NotFoundError("Notification channel not found")
        await self.repository.delete(channel)

    async def resolve_names(
        self, user_id: UUID, names: list[str]
    ) -> list[NotificationChannelDB]:
        channels = await self.repository.list_enabled_by_names(
            self.workspace_id, user_id, names
        )
        found = {channel.name.lower() for channel in channels}
        missing = [name for name in names if name.strip().lower() not in found]
        if missing:
            raise DomainValidationError(
                f"Unknown or disabled notification channels: {', '.join(missing)}"
            )
        return channels

    async def select_for_schedule(
        self, user_id: UUID, names: list[str] | None
    ) -> list[UUID]:
        if names:
            return [channel.id for channel in await self.resolve_names(user_id, names)]
        defaults = await self.repository.list_enabled_defaults(
            self.workspace_id, user_id
        )
        if not defaults:
            raise DomainValidationError(
                "No enabled default notification channel is configured"
            )
        # Keep defaults dynamic: an empty persisted selection means resolve
        # whichever channels are default when each occurrence is delivered.
        return []

    async def bind_trigger(
        self, trigger_id: UUID, channel_ids: list[UUID]
    ) -> TriggerNotificationDB:
        return await self.trigger_notifications.create(
            TriggerNotificationDB(
                trigger_id=trigger_id,
                channel_ids=[str(channel_id) for channel_id in channel_ids],
            )
        )

    async def send(
        self,
        *,
        user_id: UUID,
        title: str,
        body: str,
        agent_id: UUID | None = None,
        url: str | None = None,
        channel_ids: list[UUID] | None = None,
        channel_names: list[str] | None = None,
    ) -> NotificationChannelTestResponse:
        if channel_ids is not None and channel_names is not None:
            raise DomainValidationError(
                "Select notification channels by id or by name, not both"
            )
        if channel_ids is not None:
            channels = await self.repository.list_enabled_by_ids(
                self.workspace_id, user_id, channel_ids
            )
            if not channels:
                raise DomainValidationError(
                    "The selected notification channels are missing or disabled"
                )
        elif channel_names:
            channels = await self.resolve_names(user_id, channel_names)
        else:
            channels = await self.repository.list_enabled_defaults(
                self.workspace_id, user_id
            )
        if not channels:
            raise DomainValidationError(
                "No enabled default notification channel is configured"
            )

        clean_title = " ".join(title.split()).strip()[:150]
        clean_body = body.strip()[:10_000]
        if not clean_title or not clean_body:
            raise DomainValidationError("Notification title and body are required")
        absolute_url = (
            f"{auth_settings.FRONTEND_URL.rstrip('/')}{url}"
            if url and url.startswith("/")
            else url
        )
        delivered: list[str] = []
        failed: dict[str, str] = {}
        slack_channels: list[NotificationChannelDB] = []
        for channel in channels:
            if channel.channel_type is NotificationChannelType.browser:
                await stage_workspace_event(
                    self.db,
                    workspace_id=self.workspace_id,
                    kind=WorkspaceEventKind.notifications,
                    target_user_id=user_id,
                    payload={
                        "title": clean_title,
                        "body": clean_body,
                        **({"url": absolute_url} if absolute_url else {}),
                    },
                )
                delivered.append(channel.name)
            else:
                slack_channels.append(channel)

        # The browser outbox must commit before Slack, whose external side
        # effect cannot be rolled back if the request later fails.
        await self.db.commit()

        if slack_channels:
            bot_tokens: list[str] = []
            try:
                runtime = await SlackNotificationSettingsService(
                    self.db
                ).get_runtime_config(self.workspace_id)
                if runtime is not None:
                    bot_tokens.append(runtime.bot_token)
            except Exception:  # noqa: BLE001 — one channel must not undo the others
                logger.warning(
                    "Workspace Slack notification configuration could not be loaded",
                    exc_info=True,
                )
            if agent_id is not None:
                try:
                    configs = await AgentSlackBotService(
                        self.db, self.workspace_id
                    ).list_delivery_runtimes(agent_id)
                    bot_tokens.extend(config.bot_token for config in configs)
                except Exception:  # noqa: BLE001 — one channel must not undo the others
                    logger.warning(
                        "Agent Slack notification configuration could not be loaded",
                        exc_info=True,
                    )
            bot_tokens = list(dict.fromkeys(bot_tokens))
            if not bot_tokens:
                failed.update(
                    {
                        channel.name: (
                            "No active Slack bot is configured for this workspace "
                            "or agent"
                        )
                        for channel in slack_channels
                    }
                )
            else:
                clients = [AsyncWebClient(token=token) for token in bot_tokens]
                for channel in slack_channels:
                    channel_id = str(channel.config["channel_id"])
                    text = f"*{clean_title}*\n{clean_body}"
                    if absolute_url:
                        text += f"\n<{absolute_url}|Open in Auxilia>"
                    failure: Exception | None = None
                    for client in clients:
                        try:
                            await client.chat_postMessage(
                                channel=channel_id,
                                text=text,
                                unfurl_links=False,
                                unfurl_media=False,
                            )
                            delivered.append(channel.name)
                            failure = None
                            break
                        except SlackApiError as exc:
                            # Slack rejected this token before posting. Another
                            # configured bot may have access to the channel.
                            failure = exc
                            continue
                        except Exception as exc:  # noqa: BLE001
                            # Transport errors are ambiguous: retrying with a
                            # different token could duplicate a delivered post.
                            failure = exc
                            break
                    if failure is not None:
                        logger.warning(
                            "Notification delivery to channel %s failed",
                            channel.id,
                            exc_info=(
                                type(failure),
                                failure,
                                failure.__traceback__,
                            ),
                        )
                        failed[channel.name] = str(failure) or type(failure).__name__
        return NotificationChannelTestResponse(delivered=delivered, failed=failed)

    async def test(
        self, channel_id: UUID, user_id: UUID
    ) -> NotificationChannelTestResponse:
        return await self.send(
            user_id=user_id,
            title="Test notification",
            body="Your Auxilia notification channel is working.",
            url="/settings?tab=profile&section=notifications",
            channel_ids=[channel_id],
        )


class SlackNotificationSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SlackNotificationSettingsRepository(db)

    async def get_runtime_config(self, workspace_id: UUID) -> SlackRuntimeConfig | None:
        row = await self.repository.get_settings(workspace_id)
        if row is None or not row.enabled:
            return None
        credentials = await self.repository.get_credentials(workspace_id)
        if credentials is None or not row.slack_team_id:
            return None
        return SlackRuntimeConfig(
            workspace_id=workspace_id,
            slack_team_id=row.slack_team_id,
            bot_token=credentials[0],
            signing_secret=credentials[1],
        )

    async def get_runtime_config_for_team(
        self, team_id: str
    ) -> SlackRuntimeConfig | None:
        row = await self.repository.get_by_team_id(team_id)
        if row is None:
            return None
        return await self.get_runtime_config(row.workspace_id)

    async def list_runtime_configs(self) -> list[SlackRuntimeConfig]:
        configs: list[SlackRuntimeConfig] = []
        for row in await self.repository.list_configured():
            config = await self.get_runtime_config(row.workspace_id)
            if config is not None:
                configs.append(config)
        return configs

    async def get_response(
        self, workspace_id: UUID
    ) -> SlackNotificationSettingsResponse:
        row = await self.repository.get_settings(workspace_id)
        credentials = await self.repository.get_credentials(workspace_id)
        bot_token = credentials[0] if credentials else None
        base = f"{auth_settings.FRONTEND_URL}/api/backend/integrations/slack"
        return SlackNotificationSettingsResponse(
            enabled=bool(row and row.enabled),
            is_configured=credentials is not None,
            bot_token_last4=bot_token[-4:] if bot_token else None,
            bot_token_length=len(bot_token) if bot_token else None,
            has_signing_secret=credentials is not None,
            slack_team_id=row.slack_team_id if row else None,
            events_url=f"{base}/events",
            interactions_url=f"{base}/interactions",
        )

    async def update(
        self, workspace_id: UUID, data: SlackNotificationSettingsUpdate
    ) -> SlackNotificationSettingsResponse:
        existing = await self.repository.get_settings(workspace_id)
        bot_token = data.bot_token.strip() if data.bot_token is not None else None
        signing_secret = (
            data.signing_secret.strip() if data.signing_secret is not None else None
        )
        if (bot_token is None) != (signing_secret is None):
            raise DomainValidationError(
                "Slack bot token and signing secret must be updated together"
            )
        if bot_token is not None and not bot_token:
            raise DomainValidationError("Slack credentials cannot be empty")
        if signing_secret is not None and not signing_secret:
            raise DomainValidationError("Slack credentials cannot be empty")
        slack_team_id = (
            data.slack_team_id.strip()
            if data.slack_team_id is not None
            else existing.slack_team_id
            if existing
            else None
        )
        if bot_token is not None and not slack_team_id:
            try:
                auth = await AsyncWebClient(token=bot_token).auth_test()
                resolved_team_id = auth.get("team_id")
            except Exception as exc:
                raise DomainValidationError(
                    "Could not resolve the Slack workspace from the bot token"
                ) from exc
            if not isinstance(resolved_team_id, str) or not resolved_team_id:
                raise DomainValidationError(
                    "Slack did not return a workspace id for this bot token"
                )
            slack_team_id = resolved_team_id
        await self.repository.save(
            workspace_id=workspace_id,
            enabled=data.enabled,
            bot_token=bot_token,
            signing_secret=signing_secret,
            slack_team_id=slack_team_id,
        )
        invalidate_slack_runtime_cache()
        return await self.get_response(workspace_id)

    async def clear(self, workspace_id: UUID) -> SlackNotificationSettingsResponse:
        await self.repository.clear(workspace_id)
        invalidate_slack_runtime_cache()
        return await self.get_response(workspace_id)


def get_slack_notification_settings_service(
    db: AsyncSession = Depends(get_db),
) -> SlackNotificationSettingsService:
    return SlackNotificationSettingsService(db)


def get_notification_channel_service(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_active_workspace_id),
) -> NotificationChannelService:
    return NotificationChannelService(db, workspace_id)
