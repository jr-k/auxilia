"""Add Slack thinking message setting.

Revision ID: i7e9a1c3f5b8
Revises: h6d8f0b2e4a7
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "i7e9a1c3f5b8"
down_revision: str | Sequence[str] | None = "h6d8f0b2e4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_slack_bots",
        sa.Column(
            "show_thinking_message",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_slack_bots", "show_thinking_message")
