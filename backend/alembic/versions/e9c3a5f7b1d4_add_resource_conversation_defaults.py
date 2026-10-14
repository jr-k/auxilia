"""add resource conversation defaults

Revision ID: e9c3a5f7b1d4
Revises: d8b2c4e6f0a1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e9c3a5f7b1d4"
down_revision: str | Sequence[str] | None = "d8b2c4e6f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in ("agent_sandboxes", "agent_skills", "agent_subagents"):
        op.add_column(
            table_name,
            sa.Column(
                "enabled_by_default",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    for table_name in ("agent_subagents", "agent_skills", "agent_sandboxes"):
        op.drop_column(table_name, "enabled_by_default")
