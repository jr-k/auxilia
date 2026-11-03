"""add web push subscriptions and deliveries

Revision ID: l7b9d1f3a5c8
Revises: k6a8b0d2e4f7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "l7b9d1f3a5c8"
down_revision: str | Sequence[str] | None = "k6a8b0d2e4f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    created_at, updated_at = _timestamps()
    op.create_table(
        "web_push_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False),
        sa.Column("endpoint_encrypted", sa.Text(), nullable=False),
        sa.Column("p256dh_encrypted", sa.Text(), nullable=False),
        sa.Column("auth_encrypted", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "endpoint_hash",
            name="uq_web_push_subscriptions_endpoint_hash",
        ),
    )
    op.create_index(
        "ix_web_push_subscriptions_endpoint_hash",
        "web_push_subscriptions",
        ["endpoint_hash"],
    )
    op.create_index(
        "ix_web_push_subscriptions_user_id",
        "web_push_subscriptions",
        ["user_id"],
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "web_push_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("last_error", sa.String(length=128), nullable=True),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["web_push_subscriptions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "run_id",
            name="uq_web_push_deliveries_subscription_run",
        ),
    )
    op.create_index(
        "ix_web_push_deliveries_pending",
        "web_push_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "ix_web_push_deliveries_run_id",
        "web_push_deliveries",
        ["run_id"],
    )
    op.create_index(
        "ix_web_push_deliveries_subscription_id",
        "web_push_deliveries",
        ["subscription_id"],
    )


def downgrade() -> None:
    op.drop_table("web_push_deliveries")
    op.drop_table("web_push_subscriptions")
