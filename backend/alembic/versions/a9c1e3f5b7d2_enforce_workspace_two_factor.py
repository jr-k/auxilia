"""enforce workspace two factor

Revision ID: a9c1e3f5b7d2
Revises: f8b4c2d6e9a1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "a9c1e3f5b7d2"
down_revision: str | Sequence[str] | None = "f8b4c2d6e9a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This replay-protection column was added to an already-released migration.
    # Existing databases had already applied that revision, so repair them here;
    # fresh databases already have it and must not receive a duplicate column.
    two_factor_columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("user_two_factors")
    }
    if "last_used_totp_counter" not in two_factor_columns:
        op.add_column(
            "user_two_factors",
            sa.Column("last_used_totp_counter", sa.BigInteger(), nullable=True),
        )

    op.add_column(
        "workspace_authentication",
        sa.Column(
            "enforce_two_factor",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("workspace_authentication", "enforce_two_factor")
