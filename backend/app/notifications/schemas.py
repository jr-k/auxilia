from pydantic import BaseModel, Field, field_validator


class SlackNotificationSettingsResponse(BaseModel):
    enabled: bool


class SlackNotificationSettingsUpdate(BaseModel):
    enabled: bool = True


class WebPushConfigResponse(BaseModel):
    enabled: bool
    public_key: str | None


class WebPushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=1024)
    auth: str = Field(min_length=1, max_length=1024)


class WebPushSubscriptionUpsert(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)
    keys: WebPushSubscriptionKeys
    user_agent: str | None = Field(default=None, max_length=512)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, endpoint: str) -> str:
        if not endpoint.startswith("https://"):
            raise ValueError("A Web Push endpoint must use HTTPS")
        return endpoint


class WebPushSubscriptionDelete(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)


class WebPushSubscriptionResponse(BaseModel):
    subscribed: bool
