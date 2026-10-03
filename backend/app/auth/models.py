from sqlalchemy import CheckConstraint, Column, Text
from sqlmodel import Field

from app.models import BaseDBModel


class WorkspaceAuthenticationDB(BaseDBModel, table=True):
    __tablename__ = "workspace_authentication"
    __table_args__ = (
        CheckConstraint(
            "(google_client_id_encrypted IS NULL) = "
            "(google_client_secret_encrypted IS NULL)",
            name="ck_workspace_authentication_google_pair",
        ),
    )

    key: str = Field(default="default", nullable=False, unique=True)
    enabled: bool = Field(default=False, nullable=False)
    google_client_id_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    google_client_secret_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    google_exclusive: bool = Field(default=False, nullable=False)
