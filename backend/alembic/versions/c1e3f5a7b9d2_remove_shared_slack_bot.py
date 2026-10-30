"""remove shared Slack bot

Revision ID: c1e3f5a7b9d2
Revises: b0d2f4a6c8e1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "c1e3f5a7b9d2"
down_revision: str | Sequence[str] | None = "b0d2f4a6c8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_slack_notification_credentials_pair",
        "slack_notification_settings",
        type_="check",
    )
    op.drop_index(
        "ix_slack_notification_settings_slack_team_id",
        table_name="slack_notification_settings",
    )
    op.drop_column("slack_notification_settings", "slack_team_id")
    op.drop_column("slack_notification_settings", "bot_token_encrypted")
    op.drop_column("slack_notification_settings", "signing_secret_encrypted")


def downgrade() -> None:
    op.add_column(
        "slack_notification_settings",
        sa.Column("bot_token_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "slack_notification_settings",
        sa.Column("signing_secret_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "slack_notification_settings",
        sa.Column("slack_team_id", sa.String(), nullable=True),
    )
    op.create_check_constraint(
        "ck_slack_notification_credentials_pair",
        "slack_notification_settings",
        "(bot_token_encrypted IS NULL) = (signing_secret_encrypted IS NULL)",
    )
    op.create_index(
        "ix_slack_notification_settings_slack_team_id",
        "slack_notification_settings",
        ["slack_team_id"],
        unique=True,
    )
