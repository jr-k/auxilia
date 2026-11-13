"""add trigger notifications enabled

Revision ID: q2g4i6k8m0o3
Revises: p1f3h5j7l9n2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "q2g4i6k8m0o3"
down_revision: str | Sequence[str] | None = "p1f3h5j7l9n2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "triggers",
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("triggers", "notifications_enabled")
