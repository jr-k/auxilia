"""normalize OpenAI reasoning effort

Revision ID: b7d9f1a3c5e8
Revises: a6c8e0f2b4d7
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "b7d9f1a3c5e8"
down_revision: str | Sequence[str] | None = "a6c8e0f2b4d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize(table_name: str, model_column: str, effort_column: str) -> None:
    table = sa.table(
        table_name,
        sa.column(model_column, sa.String()),
        sa.column(effort_column, sa.String()),
    )
    compact_models = ("gpt-5", "gpt-5-mini", "gpt-5-nano")
    op.execute(
        sa.update(table)
        .where(
            table.c[model_column].in_(compact_models),
            table.c[effort_column] == "none",
        )
        .values({effort_column: "minimal"})
    )
    op.execute(
        sa.update(table)
        .where(
            table.c[model_column].in_((*compact_models, "gpt-5.1")),
            table.c[effort_column] == "xhigh",
        )
        .values({effort_column: "high"})
    )


def upgrade() -> None:
    _normalize("threads", "model_id", "reasoning_effort")
    _normalize("triggers", "model_id", "reasoning_effort")
    _normalize("agents", "default_model_id", "default_reasoning_effort")


def downgrade() -> None:
    # The old values were unsupported, and valid "minimal"/"high" selections
    # are indistinguishable from normalized rows. Reintroducing invalid values
    # would be both lossy and unsafe.
    pass
