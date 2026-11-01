from pydantic_settings import BaseSettings

from app.settings import settings_config


class WhatsAppSettings(BaseSettings):
    graph_api_version: str = "v25.0"
    request_timeout_seconds: float = 30
    media_timeout_seconds: float = 120

    model_config = settings_config(env_prefix="whatsapp_")


whatsapp_settings = WhatsAppSettings()
