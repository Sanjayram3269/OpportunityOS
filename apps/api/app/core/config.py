from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    # ── Discovery source configuration ───────────────────────────────
    remotive_api_url: str = "https://remotive.com/api/remote-jobs"
    remotive_request_timeout: int = 30  # seconds
    arbeitnow_api_url: str = "https://www.arbeitnow.com/api/job-board-api"
    arbeitnow_request_timeout: int = 30  # seconds
    himalayas_search_url: str = "https://himalayas.app/jobs/api/search"
    himalayas_request_timeout: int = 30  # seconds

    # ── AI Intelligence Layer ────────────────────────────────────────
    # AI is OPTIONAL. When ai_api_key is empty, the system works
    # with deterministic matching only.
    # Supported providers (all use OpenAI-compatible API):
    #   - HuggingFace Inference API (free tier)
    #     URL: https://api-inference.huggingface.co/models/<model>
    #     Key: HF token from https://huggingface.co/settings/tokens
    #   - OpenRouter (free models available)
    #     URL: https://openrouter.ai/api/v1/chat/completions
    #     Key: OpenRouter key from https://openrouter.ai/keys
    ai_api_url: str = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
    ai_api_key: str = ""  # Empty = AI disabled, system still works
    ai_model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    ai_timeout: int = 60  # seconds
    ai_max_tokens: int = 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()