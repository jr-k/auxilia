"""Add one default agent per workspace.

Revision ID: e1b3d5f7a9c4
Revises: d0a2c4e6f8b1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e1b3d5f7a9c4"
down_revision: str | Sequence[str] | None = "d0a2c4e6f8b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_agents_workspace_default",
        "agents",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index("uq_agents_workspace_default", table_name="agents")
    op.drop_column("agents", "is_default")
