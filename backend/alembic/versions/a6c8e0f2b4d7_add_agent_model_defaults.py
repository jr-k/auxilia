"""add agent model defaults

Revision ID: a6c8e0f2b4d7
Revises: e5f7a9c1d3b6
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "a6c8e0f2b4d7"
down_revision: str | Sequence[str] | None = "e5f7a9c1d3b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("default_model_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("default_reasoning_effort", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "default_reasoning_effort")
    op.drop_column("agents", "default_model_id")
