from pydantic import Field
from pydantic_settings import BaseSettings

from app.settings import settings_config


class OpenSandboxSettings(BaseSettings):
    """Process-wide OpenSandbox lifecycle settings."""

    # Zero asks OpenSandbox for manual cleanup instead of an expiration time.
    ttl_minutes: int = Field(default=30, ge=0)

    model_config = settings_config(env_prefix="open_sandbox_")


open_sandbox_settings = OpenSandboxSettings()
