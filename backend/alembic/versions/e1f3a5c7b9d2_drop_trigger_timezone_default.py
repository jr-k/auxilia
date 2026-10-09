"""drop trigger timezone server default

Revision ID: e1f3a5c7b9d2
Revises: d8a5b3e1f7c2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e1f3a5c7b9d2"
down_revision: str | Sequence[str] | None = "d8a5b3e1f7c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "triggers",
        "timezone",
        existing_type=sa.String(length=64),
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "triggers",
        "timezone",
        existing_type=sa.String(length=64),
        server_default="UTC",
    )
