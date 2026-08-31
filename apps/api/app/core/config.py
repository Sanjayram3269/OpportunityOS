from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    # ── Discovery source configuration ───────────────────────────────
    remotive_api_url: str = "https://remotive.com/api/remote-jobs"
    remotive_request_timeout: int = 30  # seconds

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()