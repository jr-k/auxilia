"""add MCP OAuth authorization server

Revision ID: c8f1a3e5b7d9
Revises: b7d9f1a3c5e8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "c8f1a3e5b7d9"
down_revision: str | Sequence[str] | None = "b7d9f1a3c5e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "mcp_oauth_clients",
        *_timestamps(),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mcp_oauth_clients_client_id",
        "mcp_oauth_clients",
        ["client_id"],
        unique=True,
    )

    op.create_table(
        "mcp_oauth_authorization_requests",
        *_timestamps(),
        sa.Column("handle_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("code_challenge", sa.String(length=255), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("redirect_uri_provided_explicitly", sa.Boolean(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "handle_hash",
        "client_id",
        "expires_at",
        "status",
        "user_id",
        "workspace_id",
        "code_hash",
    ):
        op.create_index(
            f"ix_mcp_oauth_authorization_requests_{column}",
            "mcp_oauth_authorization_requests",
            [column],
            unique=column in {"handle_hash", "code_hash"},
        )

    op.create_table(
        "mcp_oauth_grants",
        *_timestamps(),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("access_token_hash", sa.String(length=64), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "client_id",
        "user_id",
        "workspace_id",
        "access_token_hash",
        "access_expires_at",
        "refresh_token_hash",
        "refresh_expires_at",
    ):
        op.create_index(
            f"ix_mcp_oauth_grants_{column}",
            "mcp_oauth_grants",
            [column],
            unique=column in {"access_token_hash", "refresh_token_hash"},
        )


def downgrade() -> None:
    op.drop_table("mcp_oauth_grants")
    op.drop_table("mcp_oauth_authorization_requests")
    op.drop_table("mcp_oauth_clients")
