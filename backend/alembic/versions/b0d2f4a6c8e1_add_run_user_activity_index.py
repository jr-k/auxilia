"""add run user activity index

Revision ID: b0d2f4a6c8e1
Revises: a9c1e3f5b7d2
"""

from collections.abc import Sequence

from alembic import op


revision: str = "b0d2f4a6c8e1"
down_revision: str | Sequence[str] | None = "a9c1e3f5b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_runs_user_id_created_at",
        "runs",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_runs_user_id_created_at", table_name="runs")
