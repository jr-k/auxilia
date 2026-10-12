"""add database connections

Revision ID: b7d1e3f5a9c2
Revises: a6c9e2d4f7b1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "b7d1e3f5a9c2"
down_revision: str | Sequence[str] | None = "a6c9e2d4f7b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column("managed_by", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "mcp_servers",
        sa.Column("managed_resource_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_mcp_servers_managed_by", "mcp_servers", ["managed_by"], unique=False
    )
    op.create_index(
        "ix_mcp_servers_managed_resource_id",
        "mcp_servers",
        ["managed_resource_id"],
        unique=False,
    )

    op.create_table(
        "database_connections",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("mcp_server_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("engine", sa.String(), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("ssl_mode", sa.String(length=64), nullable=True),
        sa.Column("connection_timeout", sa.Integer(), nullable=False),
        sa.Column("query_timeout", sa.Integer(), nullable=False),
        sa.Column("readonly", sa.Boolean(), nullable=False),
        sa.Column("max_rows", sa.Integer(), nullable=False),
        sa.Column("desired_revision", sa.Integer(), nullable=False),
        sa.Column("applied_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"], ["mcp_servers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mcp_server_id"),
        sa.UniqueConstraint("source_id"),
    )
    op.create_index(
        "ix_database_connections_workspace_id",
        "database_connections",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_database_connections_owner_id",
        "database_connections",
        ["owner_id"],
        unique=False,
    )

    op.create_table(
        "database_connection_credentials",
        sa.Column("database_connection_id", sa.Uuid(), nullable=False),
        sa.Column("password_encrypted", sa.String(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["database_connection_id"],
            ["database_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("database_connection_id"),
    )

    op.create_table(
        "dbhub_control_state",
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("desired_revision", sa.Integer(), nullable=False),
        sa.Column("applied_revision", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO dbhub_control_state
                (id, key, desired_revision, applied_revision, created_at, updated_at)
            VALUES
                ('00000000-0000-0000-0000-00000000db42', 'global', 0, 0, now(), now())
            """
        )
    )


def downgrade() -> None:
    op.drop_table("dbhub_control_state")
    op.drop_table("database_connection_credentials")
    op.drop_index("ix_database_connections_owner_id", table_name="database_connections")
    op.drop_index(
        "ix_database_connections_workspace_id", table_name="database_connections"
    )
    op.drop_table("database_connections")
    op.drop_index("ix_mcp_servers_managed_resource_id", table_name="mcp_servers")
    op.drop_index("ix_mcp_servers_managed_by", table_name="mcp_servers")
    op.drop_column("mcp_servers", "managed_resource_id")
    op.drop_column("mcp_servers", "managed_by")
