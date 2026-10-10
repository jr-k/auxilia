"""add agent web search

Revision ID: e5f7a9c1d3b6
Revises: b3e7c1d9a5f2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e5f7a9c1d3b6"
down_revision: str | Sequence[str] | None = "b3e7c1d9a5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "web_search_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "web_search_enabled")
