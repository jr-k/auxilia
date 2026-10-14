"""add MCP conversation default

Revision ID: c6a8e0f2b4d5
Revises: b5f7d9a1c3e4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "c6a8e0f2b4d5"
down_revision: str | Sequence[str] | None = "b5f7d9a1c3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_mcp_servers",
        sa.Column(
            "enabled_by_default",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_mcp_servers", "enabled_by_default")
