"""Store user attachments beside agent artifacts.

Revision ID: b6d8f0a2c4e7
Revises: e5f7a9b1c3d6
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "b6d8f0a2c4e7"
down_revision: str | Sequence[str] | None = "e5f7a9b1c3d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column(
            "origin",
            sa.String(),
            nullable=False,
            server_default="artifact",
        ),
    )
    op.alter_column("artifacts", "tool_call_id", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM artifacts WHERE origin = 'attachment'")
    op.alter_column("artifacts", "tool_call_id", nullable=False)
    op.drop_column("artifacts", "origin")
