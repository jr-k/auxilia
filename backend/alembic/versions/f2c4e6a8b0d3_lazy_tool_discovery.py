"""Replace automatic tool discovery with lazy; Slack picks a discovery mode.

Revision ID: f2c4e6a8b0d3
Revises: e1b3d5f7a9c4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "f2c4e6a8b0d3"
down_revision: str | Sequence[str] | None = "e1b3d5f7a9c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The provider-native mode is gone; its agents move to the per-prompt
    # server router, the closest "let the model pick" behaviour.
    op.execute(
        "UPDATE agents SET tool_discovery_mode = 'lazy' "
        "WHERE tool_discovery_mode = 'automatic'"
    )

    op.add_column(
        "agent_slack_bots",
        sa.Column(
            "tool_discovery_mode",
            sa.String(length=16),
            server_default="all_capabilities",
            nullable=False,
        ),
    )
    # A connection that forced every capability keeps doing so; one that did
    # not inherits the mode its agent had, which is what it ran with before.
    op.execute(
        """
        UPDATE agent_slack_bots
        SET tool_discovery_mode = CASE
            WHEN force_enable_all_capabilities THEN 'all_capabilities'
            ELSE COALESCE(
                (SELECT a.tool_discovery_mode FROM agents a
                 WHERE a.id = agent_slack_bots.agent_id),
                'disabled'
            )
        END
        """
    )
    op.drop_column("agent_slack_bots", "force_enable_all_capabilities")


def downgrade() -> None:
    op.add_column(
        "agent_slack_bots",
        sa.Column(
            "force_enable_all_capabilities",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE agent_slack_bots SET force_enable_all_capabilities = "
        "(tool_discovery_mode = 'all_capabilities')"
    )
    op.drop_column("agent_slack_bots", "tool_discovery_mode")
    op.execute(
        "UPDATE agents SET tool_discovery_mode = 'automatic' "
        "WHERE tool_discovery_mode = 'lazy'"
    )
