"""allow multiple Slack bots per agent

Revision ID: d8a5b3e1f7c2
Revises: b0c3d5e7f9a1
"""

from collections.abc import Sequence

from alembic import op


revision: str = "d8a5b3e1f7c2"
down_revision: str | Sequence[str] | None = "b0c3d5e7f9a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_agent_slack_bot_agent",
        "agent_slack_bots",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_agent_slack_bot_agent",
        "agent_slack_bots",
        ["agent_id"],
    )
