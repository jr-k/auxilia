from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, Column, Enum as SAEnum, String, Text, UniqueConstraint
from sqlmodel import Field

from app.agents.models import ToolDiscoveryMode
from app.models import BaseDBModel


class SlackToolDiscoveryMode(str, Enum):
    """How a Slack connection exposes MCP tools, chosen per connection.

    The first three mirror ``ToolDiscoveryMode`` and apply it to every agent
    of the graph while preserving each resource's ``enabled_by_default``
    setting. ``all_capabilities`` explicitly re-enables every configured
    resource and loads every MCP schema eagerly.
    """

    disabled = "disabled"
    lazy = "lazy"
    local = "local"
    all_capabilities = "all_capabilities"

    @property
    def force_enable_all_capabilities(self) -> bool:
        return self is SlackToolDiscoveryMode.all_capabilities

    @property
    def runtime_mode(self) -> ToolDiscoveryMode:
        if self is SlackToolDiscoveryMode.all_capabilities:
            return ToolDiscoveryMode.disabled
        return ToolDiscoveryMode(self.value)


class AgentSlackBotDB(BaseDBModel, table=True):
    """One independently installed Slack bot representing one agent."""

    __tablename__ = "agent_slack_bots"
    __table_args__ = (
        UniqueConstraint(
            "slack_team_id",
            "bot_user_id",
            name="uq_agent_slack_bot_installation",
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    agent_id: UUID = Field(
        foreign_key="agents.id", ondelete="CASCADE", nullable=False, index=True
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    require_mention_in_threads: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    show_tool_callouts: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    show_auxilia_link: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    tool_discovery_mode: SlackToolDiscoveryMode = Field(
        default=SlackToolDiscoveryMode.all_capabilities,
        sa_column=Column(
            SAEnum(
                SlackToolDiscoveryMode,
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
            server_default=SlackToolDiscoveryMode.all_capabilities.value,
        ),
    )
    bot_token_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    signing_secret_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    slack_team_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    slack_team_name: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    bot_user_id: str = Field(sa_column=Column(String(64), nullable=False))
    bot_name: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )


class SlackIdentityDB(BaseDBModel, table=True):
    __tablename__ = "slack_identities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "slack_team_id",
            "slack_user_id",
            name="uq_slack_identity_external",
        ),
        UniqueConstraint(
            "workspace_id",
            "slack_team_id",
            "user_id",
            name="uq_slack_identity_internal",
        ),
    )

    workspace_id: UUID = Field(
        foreign_key="workspaces.id", ondelete="CASCADE", nullable=False, index=True
    )
    slack_team_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    slack_user_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    user_id: UUID = Field(
        foreign_key="users.id", ondelete="CASCADE", nullable=False, index=True
    )


class SlackThreadBindingDB(BaseDBModel, table=True):
    """Maps Slack's external thread coordinates to an internal Auxilia thread."""

    __tablename__ = "slack_thread_bindings"
    __table_args__ = (
        UniqueConstraint(
            "slack_bot_id",
            "channel_id",
            "slack_thread_ts",
            name="uq_slack_thread_external",
        ),
        UniqueConstraint("thread_id", name="uq_slack_thread_internal"),
    )

    slack_bot_id: UUID = Field(
        foreign_key="agent_slack_bots.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    thread_id: str = Field(
        foreign_key="threads.id", ondelete="CASCADE", nullable=False, index=True
    )
    channel_id: str = Field(max_length=64, nullable=False)
    slack_thread_ts: str = Field(max_length=64, nullable=False)
    slack_user_id: str = Field(max_length=64, nullable=False)
    last_context_ts: str | None = Field(default=None, max_length=64)
