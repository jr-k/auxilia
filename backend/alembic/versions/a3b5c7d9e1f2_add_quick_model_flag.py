"""Add the workspace quick model flag.

Revision ID: a3b5c7d9e1f2
Revises: f2c4e6a8b0d3
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "a3b5c7d9e1f2"
down_revision: str | Sequence[str] | None = "f2c4e6a8b0d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Starts unset: the runtime falls back to the thread's model at minimal
    # effort until an admin flags a quick model.
    op.add_column(
        "models",
        sa.Column(
            "is_quick", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.create_index(
        "uq_models_single_quick",
        "models",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("is_quick"),
        sqlite_where=sa.text("is_quick"),
    )


def downgrade() -> None:
    op.drop_index("uq_models_single_quick", table_name="models")
    op.drop_column("models", "is_quick")
