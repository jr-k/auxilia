"""remove unsupported model rows

Revision ID: n9d1f3a5c7e2
Revises: m8c0e2f4b6d9
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "n9d1f3a5c7e2"
down_revision: str | Sequence[str] | None = "m8c0e2f4b6d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REMOVED_MODELS: tuple[tuple[str, str], ...] = (
    ("google", "gemini-3-pro-preview"),
    ("meta", "muse-spark-1.1"),
    ("openrouter", "glm-5.2-high"),
    ("openrouter", "glm-5.2-max"),
    ("openrouter", "qwen/qwen3.8-max"),
)


def upgrade() -> None:
    models = sa.table(
        "models",
        sa.column("provider", sa.String()),
        sa.column("model_id", sa.String()),
    )
    predicates = [
        sa.and_(models.c.provider == provider, models.c.model_id == model_id)
        for provider, model_id in REMOVED_MODELS
    ]
    op.execute(sa.delete(models).where(sa.or_(*predicates)))


def downgrade() -> None:
    # Workspace enablement choices cannot be reconstructed after removal.
    pass
