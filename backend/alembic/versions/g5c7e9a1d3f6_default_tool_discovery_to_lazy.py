"""default tool discovery to lazy

Revision ID: g5c7e9a1d3f6
Revises: f4b6d8a0c2e5
"""

from collections.abc import Sequence

from alembic import op


revision: str = "g5c7e9a1d3f6"
down_revision: str | Sequence[str] | None = "f4b6d8a0c2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("agents", "tool_discovery_mode", server_default="lazy")
    op.alter_column(
        "agent_slack_bots",
        "tool_discovery_mode",
        server_default="lazy",
    )
    op.alter_column(
        "agent_telegram_bots",
        "tool_discovery_mode",
        server_default="lazy",
    )


def downgrade() -> None:
    op.alter_column(
        "agent_telegram_bots",
        "tool_discovery_mode",
        server_default="all_capabilities",
    )
    op.alter_column(
        "agent_slack_bots",
        "tool_discovery_mode",
        server_default="all_capabilities",
    )
    op.alter_column("agents", "tool_discovery_mode", server_default="disabled")
