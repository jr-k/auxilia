"""add notification badge

Revision ID: o0e2g4i6k8m1
Revises: n9d1f3a5c7e2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "o0e2g4i6k8m1"
down_revision: str | Sequence[str] | None = "n9d1f3a5c7e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instance_appearance",
        sa.Column("notification_badge_data", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "instance_appearance",
        sa.Column(
            "notification_badge_media_type",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "instance_appearance",
        sa.Column(
            "notification_badge_sha256",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "instance_appearance",
        sa.Column("notification_badge_revision", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("instance_appearance", "notification_badge_revision")
    op.drop_column("instance_appearance", "notification_badge_sha256")
    op.drop_column("instance_appearance", "notification_badge_media_type")
    op.drop_column("instance_appearance", "notification_badge_data")
