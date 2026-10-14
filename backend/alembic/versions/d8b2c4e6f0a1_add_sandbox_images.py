"""add sandbox images

Revision ID: d8b2c4e6f0a1
Revises: c6a8e0f2b4d5
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "d8b2c4e6f0a1"
down_revision: str | Sequence[str] | None = "c6a8e0f2b4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sandboxes", sa.Column("image_revision", sa.Uuid(), nullable=True))
    op.create_table(
        "sandbox_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sandbox_id", sa.Uuid(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("media_type", sa.String(length=50), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["sandbox_id"], ["sandboxes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sandbox_id", name="uq_sandbox_image_sandbox_id"),
    )
    op.create_index(
        op.f("ix_sandbox_images_sandbox_id"),
        "sandbox_images",
        ["sandbox_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sandbox_images_sandbox_id"),
        table_name="sandbox_images",
    )
    op.drop_table("sandbox_images")
    op.drop_column("sandboxes", "image_revision")
