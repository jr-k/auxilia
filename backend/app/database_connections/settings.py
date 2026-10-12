from pathlib import Path

from pydantic_settings import BaseSettings

from app.settings import BACKEND_DIR, settings_config


class DBHubSettings(BaseSettings):
    enabled: bool = False
    url: str = "http://localhost:8080"
    auth_token: str = ""
    config_path: Path = BACKEND_DIR.parent / ".runtime" / "dbhub" / "dbhub.toml"
    reconcile_interval_seconds: float = 2.0

    model_config = settings_config(env_prefix="dbhub_")

    @property
    def mcp_url(self) -> str:
        return f"{self.url.rstrip('/')}/mcp"


dbhub_settings = DBHubSettings()
