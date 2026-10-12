from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.repository import AgentRepository
from app.auth.settings import auth_settings
from app.database import get_db
from app.exceptions import AlreadyExistsError, DomainValidationError, NotFoundError
from app.integrations.slack.db_models import AgentSlackBotDB
from app.integrations.slack.repository import AgentSlackBotRepository
from app.integrations.slack.schemas import AgentSlackBotResponse, AgentSlackBotUpdate
from app.notifications.repository import SlackNotificationSettingsRepository
from app.utils.encryption import decrypt_value, encrypt_value
from app.workspaces.dependencies import get_active_workspace_id


@dataclass(frozen=True)
class AgentSlackRuntimeConfig:
    id: UUID
    workspace_id: UUID
    agent_id: UUID
    enabled: bool
    require_mention_in_threads: bool
    show_tool_callouts: bool
    workspace_enabled: bool
    bot_token: str
    signing_secret: str
    slack_team_id: str
    bot_user_id: str


class AgentSlackBotService:
    def __init__(self, db: AsyncSession, workspace_id: UUID | None = None):
        self.db = db
        self.workspace_id = workspace_id
        self.repository = AgentSlackBotRepository(db)

    @staticmethod
    def _urls(agent_id: UUID) -> tuple[str, str]:
        base = (
            f"{auth_settings.FRONTEND_URL}/api/backend/integrations/slack/"
            f"agents/{agent_id}"
        )
        return f"{base}/events", f"{base}/interactions"

    @staticmethod
    def _manifest(
        agent_name: str, events_url: str, interactions_url: str
    ) -> dict[str, Any]:
        display_name = agent_name.strip()[:35] or "Agent"
        return {
            "_metadata": {"major_version": 1},
            "display_information": {
                "name": display_name,
                "description": f"{display_name} Slack bot.",
                "background_color": "#16606E",
            },
            "features": {
                "app_home": {
                    "home_tab_enabled": False,
                    "messages_tab_enabled": True,
                    "messages_tab_read_only_enabled": False,
                },
                "bot_user": {
                    "display_name": display_name,
                    "always_online": False,
                },
                "shortcuts": [
                    {
                        "name": "Ask agent about message",
                        "type": "message",
                        "callback_id": "agent_message_shortcut",
                        "description": "Use this message as context for the agent",
                    }
                ],
            },
            "oauth_config": {
                "scopes": {
                    "bot": [
                        "app_mentions:read",
                        "channels:history",
                        "chat:write",
                        "commands",
                        "im:history",
                        "im:write",
                        "users:read",
                        "users:read.email",
                    ]
                }
            },
            "settings": {
                "event_subscriptions": {
                    "request_url": events_url,
                    "bot_events": [
                        "app_mention",
                        "message.channels",
                        "message.im",
                    ],
                },
                "interactivity": {
                    "is_enabled": True,
                    "request_url": interactions_url,
                },
                "org_deploy_enabled": False,
                "socket_mode_enabled": False,
                "token_rotation_enabled": False,
            },
        }

    async def _workspace_enabled(self, workspace_id: UUID) -> bool:
        row = await SlackNotificationSettingsRepository(self.db).get_settings(
            workspace_id
        )
        return bool(row and row.enabled)

    async def _agent_name(self, workspace_id: UUID, agent_id: UUID) -> str:
        agent = await AgentRepository(self.db, workspace_id).get_scoped(agent_id)
        if agent is None:
            raise NotFoundError("Agent not found")
        return agent.name

    def _response(
        self,
        agent_id: UUID,
        agent_name: str,
        workspace_enabled: bool,
        row: AgentSlackBotDB | None = None,
    ) -> AgentSlackBotResponse:
        events_url, interactions_url = self._urls(agent_id)
        return AgentSlackBotResponse(
            id=row.id if row else None,
            workspace_enabled=workspace_enabled,
            enabled=row.enabled if row else True,
            require_mention_in_threads=(
                row.require_mention_in_threads if row else True
            ),
            show_tool_callouts=row.show_tool_callouts if row else True,
            is_configured=row is not None,
            bot_token_last4=(
                decrypt_value(row.bot_token_encrypted)[-4:] if row else None
            ),
            has_signing_secret=row is not None,
            slack_team_id=row.slack_team_id if row else None,
            slack_team_name=row.slack_team_name if row else None,
            bot_user_id=row.bot_user_id if row else None,
            bot_name=row.bot_name if row else None,
            events_url=events_url,
            interactions_url=interactions_url,
            manifest=self._manifest(agent_name, events_url, interactions_url),
        )

    async def get_setup(self, agent_id: UUID) -> AgentSlackBotResponse:
        if self.workspace_id is None:
            raise RuntimeError("A workspace is required for agent Slack settings")
        agent_name = await self._agent_name(self.workspace_id, agent_id)
        return self._response(
            agent_id,
            agent_name,
            await self._workspace_enabled(self.workspace_id),
        )

    async def list_connections(self, agent_id: UUID) -> list[AgentSlackBotResponse]:
        if self.workspace_id is None:
            raise RuntimeError("A workspace is required for agent Slack settings")
        agent_name = await self._agent_name(self.workspace_id, agent_id)
        workspace_enabled = await self._workspace_enabled(self.workspace_id)
        rows = await self.repository.list_for_agent(self.workspace_id, agent_id)
        return [
            self._response(agent_id, agent_name, workspace_enabled, row) for row in rows
        ]

    async def _validated_installation(
        self,
        token: str,
        *,
        current_id: UUID | None = None,
    ) -> tuple[Any, str, str]:
        try:
            auth = await AsyncWebClient(token=token).auth_test()
        except Exception as exc:
            raise DomainValidationError(
                "Could not validate the Slack bot token"
            ) from exc
        team_id = auth.get("team_id")
        bot_user_id = auth.get("user_id")
        if not isinstance(team_id, str) or not team_id:
            raise DomainValidationError("Slack did not return a workspace id")
        if not isinstance(bot_user_id, str) or not bot_user_id:
            raise DomainValidationError("Slack did not return a bot user id")
        existing = await self.repository.get_by_installation(team_id, bot_user_id)
        if existing is not None and existing.id != current_id:
            raise AlreadyExistsError(
                "This Slack bot is already connected to another agent"
            )
        return auth, team_id, bot_user_id

    async def create(
        self, agent_id: UUID, data: AgentSlackBotUpdate
    ) -> AgentSlackBotResponse:
        if self.workspace_id is None:
            raise RuntimeError("A workspace is required for agent Slack settings")
        agent_name = await self._agent_name(self.workspace_id, agent_id)
        token = data.bot_token.strip() if data.bot_token is not None else None
        secret = (
            data.signing_secret.strip() if data.signing_secret is not None else None
        )
        if not token or not secret:
            raise DomainValidationError(
                "Slack credentials are required to connect this agent"
            )
        auth, team_id, bot_user_id = await self._validated_installation(token)
        row = AgentSlackBotDB(
            workspace_id=self.workspace_id,
            agent_id=agent_id,
            enabled=data.enabled,
            require_mention_in_threads=data.require_mention_in_threads,
            show_tool_callouts=data.show_tool_callouts,
            bot_token_encrypted=encrypt_value(token),
            signing_secret_encrypted=encrypt_value(secret),
            slack_team_id=team_id,
            slack_team_name=auth.get("team"),
            bot_user_id=bot_user_id,
            bot_name=auth.get("user"),
        )
        self.db.add(row)
        await self.db.flush()
        return self._response(
            agent_id,
            agent_name,
            await self._workspace_enabled(self.workspace_id),
            row,
        )

    async def update(
        self, agent_id: UUID, bot_id: UUID, data: AgentSlackBotUpdate
    ) -> AgentSlackBotResponse:
        if self.workspace_id is None:
            raise RuntimeError("A workspace is required for agent Slack settings")
        agent_name = await self._agent_name(self.workspace_id, agent_id)
        row = await self.repository.get_for_agent(self.workspace_id, agent_id, bot_id)
        if row is None:
            raise NotFoundError("Slack connection not found")
        token = data.bot_token.strip() if data.bot_token is not None else None
        secret = (
            data.signing_secret.strip() if data.signing_secret is not None else None
        )
        if (token is None) != (secret is None):
            raise DomainValidationError(
                "Slack bot token and signing secret must be updated together"
            )
        if token is not None and secret is not None:
            if not token or not secret:
                raise DomainValidationError("Slack credentials cannot be empty")
            auth, team_id, bot_user_id = await self._validated_installation(
                token, current_id=row.id
            )
            row.bot_token_encrypted = encrypt_value(token)
            row.signing_secret_encrypted = encrypt_value(secret)
            row.slack_team_id = team_id
            row.slack_team_name = auth.get("team")
            row.bot_user_id = bot_user_id
            row.bot_name = auth.get("user")
        row.enabled = data.enabled
        row.require_mention_in_threads = data.require_mention_in_threads
        row.show_tool_callouts = data.show_tool_callouts
        self.db.add(row)
        await self.db.flush()
        return self._response(
            agent_id,
            agent_name,
            await self._workspace_enabled(self.workspace_id),
            row,
        )

    async def delete(self, agent_id: UUID, bot_id: UUID) -> None:
        if self.workspace_id is None:
            raise RuntimeError("A workspace is required for agent Slack settings")
        await self._agent_name(self.workspace_id, agent_id)
        row = await self.repository.get_for_agent(self.workspace_id, agent_id, bot_id)
        if row is None:
            raise NotFoundError("Slack connection not found")
        await self.repository.delete(row)

    async def list_for_verification(
        self, agent_id: UUID
    ) -> list[AgentSlackRuntimeConfig]:
        stmt_workspace_id = self.workspace_id
        if stmt_workspace_id is None:
            agent = await AgentRepository(self.db).get(agent_id)
            if agent is None:
                return []
            stmt_workspace_id = agent.workspace_id
        rows = await self.repository.list_for_agent(stmt_workspace_id, agent_id)
        workspace_enabled = await self._workspace_enabled(stmt_workspace_id)
        return [
            await self._runtime_config(row, workspace_enabled=workspace_enabled)
            for row in rows
        ]

    async def get_runtime(
        self, bot_id: UUID, *, require_active: bool = True
    ) -> AgentSlackRuntimeConfig | None:
        row = await self.repository.get_runtime(bot_id)
        if row is None:
            return None
        config = await self._runtime_config(row)
        if require_active and not (config.enabled and config.workspace_enabled):
            return None
        return config

    async def _runtime_config(
        self,
        row: AgentSlackBotDB,
        *,
        workspace_enabled: bool | None = None,
    ) -> AgentSlackRuntimeConfig:
        return AgentSlackRuntimeConfig(
            id=row.id,
            workspace_id=row.workspace_id,
            agent_id=row.agent_id,
            enabled=row.enabled,
            require_mention_in_threads=row.require_mention_in_threads,
            show_tool_callouts=row.show_tool_callouts,
            workspace_enabled=(
                workspace_enabled
                if workspace_enabled is not None
                else await self._workspace_enabled(row.workspace_id)
            ),
            bot_token=decrypt_value(row.bot_token_encrypted),
            signing_secret=decrypt_value(row.signing_secret_encrypted),
            slack_team_id=row.slack_team_id,
            bot_user_id=row.bot_user_id,
        )


def get_agent_slack_bot_service(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_active_workspace_id),
) -> AgentSlackBotService:
    return AgentSlackBotService(db, workspace_id)
