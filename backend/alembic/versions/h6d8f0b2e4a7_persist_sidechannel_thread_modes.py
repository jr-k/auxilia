"""Persist side-channel discovery modes on their conversations.

Revision ID: h6d8f0b2e4a7
Revises: g5c7e9a1d3f6
"""

from collections.abc import Sequence

from alembic import op


revision: str = "h6d8f0b2e4a7"
down_revision: str | Sequence[str] | None = "g5c7e9a1d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_THREAD_MODE_CASE = """
CASE bot.tool_discovery_mode
    WHEN 'disabled' THEN 'eager'
    WHEN 'lazy' THEN 'lazy'
    WHEN 'local' THEN 'precision'
    WHEN 'all_capabilities' THEN 'force_all'
END
"""


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE threads AS thread
        SET tool_mode = {_THREAD_MODE_CASE}
        FROM slack_thread_bindings AS binding
        JOIN agent_slack_bots AS bot ON bot.id = binding.slack_bot_id
        WHERE thread.id = binding.thread_id
          AND thread.source = 'slack'
          AND thread.tool_mode IS NULL
        """
    )
    op.execute(
        f"""
        UPDATE threads AS thread
        SET tool_mode = {_THREAD_MODE_CASE}
        FROM telegram_thread_bindings AS binding
        JOIN agent_telegram_bots AS bot ON bot.id = binding.telegram_bot_id
        WHERE thread.id = binding.thread_id
          AND thread.source = 'telegram'
          AND thread.tool_mode IS NULL
        """
    )


def downgrade() -> None:
    # The previous NULL cannot be distinguished from a user selecting
    # "Agent default" after this migration, so the data change is irreversible.
    pass
