"""add Slack identities

Revision ID: f4b6d8a0c2e5
Revises: e3a5c7f9b1d4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "f4b6d8a0c2e5"
down_revision: str | Sequence[str] | None = "e3a5c7f9b1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "slack_identities",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("slack_team_id", sa.String(length=64), nullable=False),
        sa.Column("slack_user_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_slack_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_slack_identities_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_slack_identities")),
        sa.UniqueConstraint(
            "workspace_id",
            "slack_team_id",
            "slack_user_id",
            name="uq_slack_identity_external",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "slack_team_id",
            "user_id",
            name="uq_slack_identity_internal",
        ),
    )
    op.create_index(
        op.f("ix_slack_identities_workspace_id"),
        "slack_identities",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_slack_identities_slack_team_id"),
        "slack_identities",
        ["slack_team_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_slack_identities_slack_user_id"),
        "slack_identities",
        ["slack_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_slack_identities_user_id"),
        "slack_identities",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_slack_identities_user_id"), table_name="slack_identities")
    op.drop_index(
        op.f("ix_slack_identities_slack_user_id"),
        table_name="slack_identities",
    )
    op.drop_index(
        op.f("ix_slack_identities_slack_team_id"),
        table_name="slack_identities",
    )
    op.drop_index(
        op.f("ix_slack_identities_workspace_id"),
        table_name="slack_identities",
    )
    op.drop_table("slack_identities")
