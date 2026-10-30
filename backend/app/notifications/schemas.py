from pydantic import BaseModel


class SlackNotificationSettingsResponse(BaseModel):
    enabled: bool


class SlackNotificationSettingsUpdate(BaseModel):
    enabled: bool = True
