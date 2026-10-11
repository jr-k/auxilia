"""add Ollama provider models

Revision ID: d2f6a8c0e4b1
Revises: c8f1a3e5b7d9
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "d2f6a8c0e4b1"
down_revision: str | Sequence[str] | None = "c8f1a3e5b7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "model_provider_credentials",
        "api_key_encrypted",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.add_column(
        "model_provider_credentials",
        sa.Column("base_url", sa.Text(), nullable=True),
    )
    op.create_table(
        "model_provider_catalog_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("runtime_model_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("chef", sa.String(), nullable=False),
        sa.Column("chef_slug", sa.String(), nullable=False),
        sa.Column(
            "multimodal", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "supports_structured_output",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "supports_tools", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "is_available", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "provider",
            "model_id",
            name="uq_model_provider_catalog_workspace_provider_model",
        ),
    )
    op.create_index(
        "ix_model_provider_catalog_entries_workspace_id",
        "model_provider_catalog_entries",
        ["workspace_id"],
    )
    op.create_index(
        "ix_model_provider_catalog_entries_provider",
        "model_provider_catalog_entries",
        ["provider"],
    )


def downgrade() -> None:
    op.drop_table("model_provider_catalog_entries")
    op.drop_column("model_provider_credentials", "base_url")
    op.execute("DELETE FROM model_provider_credentials WHERE api_key_encrypted IS NULL")
    op.alter_column(
        "model_provider_credentials",
        "api_key_encrypted",
        existing_type=sa.Text(),
        nullable=False,
    )
