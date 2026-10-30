from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.models import BaseDBModel


class SlackNotificationSettingsDB(BaseDBModel, table=True):
    __tablename__ = "slack_notification_settings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "key", name="uq_slack_notifications_workspace_key"
        ),
    )

    workspace_id: UUID = Field(foreign_key="workspaces.id", index=True)
    key: str = Field(default="default", nullable=False)
    enabled: bool = Field(default=False, nullable=False)
