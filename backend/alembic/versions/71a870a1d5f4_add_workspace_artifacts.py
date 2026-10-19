"""Persist workspace-scoped artifact descriptors.

Revision ID: 71a870a1d5f4
Revises: f6a8c0e2b4d7
Create Date: 2026-10-19 20:29:52.078406

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "71a870a1d5f4"
down_revision: str | Sequence[str] | None = "f6a8c0e2b4d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            sa.String(),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *[
            sa.Column(name, sa.String(), nullable=False)
            for name in [
                "tool_call_id",
                "source_path",
                "title",
                "filename",
                "mime_type",
                "sha256",
                "storage_kind",
                "storage_key",
            ]
        ],
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_bucket", sa.String(), nullable=True),
        sa.Column("storage_endpoint", sa.String(), nullable=True),
        sa.Column(
            "sandbox_source_id",
            sa.Uuid(),
            sa.ForeignKey("sandboxes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sandbox_id", sa.String(), nullable=True),
        sa.UniqueConstraint(
            "workspace_id",
            "thread_id",
            "tool_call_id",
            "source_path",
            name="uq_artifacts_workspace_thread_call_path",
        ),
    )
    op.create_index("ix_artifacts_workspace_id", "artifacts", ["workspace_id"])
    op.create_index("ix_artifacts_thread_id", "artifacts", ["thread_id"])


def downgrade() -> None:
    op.drop_table("artifacts")
