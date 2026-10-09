"""add custom HTTP MCP auth type

Revision ID: b0c3d5e7f9a1
Revises: f9b2d4e6a8c0
"""

from collections.abc import Sequence

from alembic import op


revision: str = "b0c3d5e7f9a1"
down_revision: str | Sequence[str] | None = "f9b2d4e6a8c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE mcp_auth_type ADD VALUE IF NOT EXISTS 'custom_http'")


def downgrade() -> None:
    op.execute(
        "DELETE FROM mcp_server_service_credentials "
        "WHERE mcp_server_id IN ("
        "SELECT id FROM mcp_servers WHERE auth_type = 'custom_http'"
        ")"
    )
    op.execute(
        "UPDATE mcp_servers SET auth_type = 'none' WHERE auth_type = 'custom_http'"
    )
    op.execute(
        "ALTER TABLE mcp_servers ALTER COLUMN auth_type TYPE text USING auth_type::text"
    )
    op.execute("DROP TYPE mcp_auth_type")
    op.execute(
        "CREATE TYPE mcp_auth_type AS ENUM "
        "('none', 'api_key', 'oauth2', 'service_identity')"
    )
    op.execute(
        "ALTER TABLE mcp_servers ALTER COLUMN auth_type TYPE mcp_auth_type "
        "USING auth_type::mcp_auth_type"
    )
