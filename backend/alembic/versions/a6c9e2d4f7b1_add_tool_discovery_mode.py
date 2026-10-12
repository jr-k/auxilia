"""add tool discovery mode

Revision ID: a6c9e2d4f7b1
Revises: f4b8d1c3e6a9
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "a6c9e2d4f7b1"
down_revision: str | Sequence[str] | None = "f4b8d1c3e6a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "tool_discovery_mode",
            sa.String(length=16),
            server_default="disabled",
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE agents SET tool_discovery_mode = 'automatic' "
        "WHERE tool_discovery_enabled IS TRUE"
    )
    op.drop_column("agents", "tool_discovery_enabled")


def downgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "tool_discovery_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE agents SET tool_discovery_enabled = (tool_discovery_mode <> 'disabled')"
    )
    op.drop_column("agents", "tool_discovery_mode")
