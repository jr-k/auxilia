from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings

from app.settings import settings_config


TWO_FACTOR_CHALLENGE_COOKIE = "two_factor_challenge"


class AuthSettings(BaseSettings):
    # JWT Configuration
    JWT_SECRET_KEY: str = Field(
        default="change-me-in-production",
        validation_alias=AliasChoices(
            "BACKEND_JWT_SECRET_KEY",
            "JWT_SECRET_KEY",
        ),
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    SESSION_MAX_DAYS: int = Field(default=30, ge=1)
    REMEMBER_ME_DAYS: int = Field(default=3650, ge=1)

    # Cookie Configuration
    COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "BACKEND_COOKIE_SECURE",
            "COOKIE_SECURE",
        ),
    )
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None

    # Frontend URL for OAuth redirects
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = settings_config()

    @field_validator("COOKIE_SAMESITE", mode="before")
    @classmethod
    def _lowercase_samesite(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value


auth_settings = AuthSettings()
