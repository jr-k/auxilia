from uuid import UUID

from sqlmodel import SQLModel


class SupervisionStartRequest(SQLModel):
    user_id: UUID
    workspace_id: UUID
