"""add preferences onboarding version

Revision ID: p1f3h5j7l9n2
Revises: o0e2g4i6k8m1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "p1f3h5j7l9n2"
down_revision: str | Sequence[str] | None = "o0e2g4i6k8m1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferences_onboarding_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferences_onboarding_version")
