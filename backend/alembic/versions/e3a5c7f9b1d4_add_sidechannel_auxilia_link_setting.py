"""add side-channel Auxilia link setting

Revision ID: e3a5c7f9b1d4
Revises: d2f4a6c8e0b1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e3a5c7f9b1d4"
down_revision: str | Sequence[str] | None = "d2f4a6c8e0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in ("agent_slack_bots", "agent_telegram_bots"):
        op.add_column(
            table_name,
            sa.Column(
                "show_auxilia_link",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    for table_name in ("agent_telegram_bots", "agent_slack_bots"):
        op.drop_column(table_name, "show_auxilia_link")
