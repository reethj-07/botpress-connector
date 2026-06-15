from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite:///./botpress_connector.db")
    botpress_chat_base_url: str = Field(default="https://chat.botpress.cloud")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    static_dir: Path = Field(default=Path(__file__).resolve().parents[1] / "static")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

