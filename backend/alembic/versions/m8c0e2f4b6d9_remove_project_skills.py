"""remove project skill bindings

Revision ID: m8c0e2f4b6d9
Revises: l7b9d1f3a5c8
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "m8c0e2f4b6d9"
down_revision: str | Sequence[str] | None = "l7b9d1f3a5c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Project-only selections become meaningless once bindings disappear.
    # Preserve exclusions that still target the thread or trigger's agent graph.
    op.execute(
        """
        UPDATE threads AS thread
        SET disabled_skill_ids = (
            SELECT COALESCE(
                jsonb_agg(item.value ORDER BY item.ordinality),
                '[]'::jsonb
            )
            FROM jsonb_array_elements_text(thread.disabled_skill_ids)
                WITH ORDINALITY AS item(value, ordinality)
            WHERE EXISTS (
                SELECT 1
                FROM agent_skills AS binding
                WHERE binding.skill_id::text = item.value
                  AND (
                      binding.agent_id = thread.agent_id
                      OR binding.agent_id IN (
                          SELECT link.subagent_id
                          FROM agent_subagents AS link
                          WHERE link.supervisor_id = thread.agent_id
                      )
                  )
            )
        )
        """
    )
    op.execute(
        """
        UPDATE triggers AS trigger
        SET disabled_skill_ids = (
            SELECT COALESCE(
                jsonb_agg(item.value ORDER BY item.ordinality),
                '[]'::jsonb
            )
            FROM jsonb_array_elements_text(trigger.disabled_skill_ids)
                WITH ORDINALITY AS item(value, ordinality)
            WHERE EXISTS (
                SELECT 1
                FROM agent_skills AS binding
                WHERE binding.skill_id::text = item.value
                  AND (
                      binding.agent_id = trigger.agent_id
                      OR binding.agent_id IN (
                          SELECT link.subagent_id
                          FROM agent_subagents AS link
                          WHERE link.supervisor_id = trigger.agent_id
                      )
                  )
            )
        )
        WHERE trigger.disabled_skill_ids IS NOT NULL
        """
    )
    op.drop_table("project_skills")


def downgrade() -> None:
    op.create_table(
        "project_skills",
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
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "skill_id"),
    )
    op.create_index("ix_project_skills_skill_id", "project_skills", ["skill_id"])
