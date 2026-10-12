"""add agent tool discovery

Revision ID: f4b8d1c3e6a9
Revises: e3a7c9f1b5d2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "f4b8d1c3e6a9"
down_revision: str | Sequence[str] | None = "e3a7c9f1b5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "tool_discovery_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "tool_discovery_enabled")
