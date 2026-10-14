"""add Slack capability override

Revision ID: f6a8c0e2b4d7
Revises: e9c3a5f7b1d4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f6a8c0e2b4d7"
down_revision: str | Sequence[str] | None = "e9c3a5f7b1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_slack_bots",
        sa.Column(
            "force_enable_all_capabilities",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_slack_bots", "force_enable_all_capabilities")
