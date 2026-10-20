"""add trigger resource preferences

Revision ID: d4e6f8a0b2c5
Revises: 71a870a1d5f4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "d4e6f8a0b2c5"
down_revision: str | Sequence[str] | None = "71a870a1d5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in (
        "disabled_mcp_server_ids",
        "disabled_skill_ids",
        "disabled_sandbox_ids",
        "disabled_subagent_ids",
    ):
        op.add_column(
            "triggers",
            sa.Column(
                name,
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    for name in (
        "disabled_subagent_ids",
        "disabled_sandbox_ids",
        "disabled_skill_ids",
        "disabled_mcp_server_ids",
    ):
        op.drop_column("triggers", name)
