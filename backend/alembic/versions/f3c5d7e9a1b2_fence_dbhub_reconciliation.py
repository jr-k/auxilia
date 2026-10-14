"""fence DBHub reconciliation across rolling upgrades

Revision ID: f3c5d7e9a1b2
Revises: e2b4c6d8f0a1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "f3c5d7e9a1b2"
down_revision: str | Sequence[str] | None = "e2b4c6d8f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dbhub_control_state",
        sa.Column(
            "last_successful_revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE dbhub_control_state "
            "SET last_successful_revision = applied_revision, "
            "last_error = CASE "
            "WHEN desired_revision <> applied_revision AND last_error IS NULL "
            "THEN 'GeneratedConfigPending' ELSE last_error END, "
            "applied_revision = desired_revision"
        )
    )
    op.create_check_constraint(
        "ck_dbhub_control_state_reconcile_fence",
        "dbhub_control_state",
        "desired_revision = applied_revision OR last_error IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_dbhub_control_state_reconcile_fence",
        "dbhub_control_state",
        type_="check",
    )
    op.execute(
        sa.text(
            "UPDATE dbhub_control_state SET applied_revision = last_successful_revision"
        )
    )
    op.drop_column("dbhub_control_state", "last_successful_revision")
