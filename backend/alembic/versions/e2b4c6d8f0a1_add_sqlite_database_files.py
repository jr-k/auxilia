"""add SQLite database files

Revision ID: e2b4c6d8f0a1
Revises: d9f3a5c7e1b4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e2b4c6d8f0a1"
down_revision: str | Sequence[str] | None = "d9f3a5c7e1b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "database_files",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        "ix_database_files_workspace_id",
        "database_files",
        ["workspace_id"],
    )
    op.create_index(
        "ix_database_files_owner_id",
        "database_files",
        ["owner_id"],
    )

    op.alter_column("database_connections", "host", nullable=True)
    op.alter_column("database_connections", "port", nullable=True)
    op.alter_column("database_connections", "username", nullable=True)
    op.add_column(
        "database_connections",
        sa.Column("sqlite_file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_database_connections_sqlite_file_id",
        "database_connections",
        "database_files",
        ["sqlite_file_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_database_connections_sqlite_file_id",
        "database_connections",
        ["sqlite_file_id"],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM mcp_servers WHERE id IN "
            "(SELECT mcp_server_id FROM database_connections WHERE engine = 'sqlite')"
        )
    )
    op.drop_index(
        "ix_database_connections_sqlite_file_id",
        table_name="database_connections",
    )
    op.drop_constraint(
        "fk_database_connections_sqlite_file_id",
        "database_connections",
        type_="foreignkey",
    )
    op.drop_column("database_connections", "sqlite_file_id")
    op.alter_column("database_connections", "username", nullable=False)
    op.alter_column("database_connections", "port", nullable=False)
    op.alter_column("database_connections", "host", nullable=False)
    op.drop_index("ix_database_files_owner_id", table_name="database_files")
    op.drop_index("ix_database_files_workspace_id", table_name="database_files")
    op.drop_table("database_files")
