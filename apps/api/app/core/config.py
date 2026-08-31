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

    # ── Email Delivery ──────────────────────────────────────────────
    # Email is OPTIONAL. When email_host is empty, sending is disabled.
    # The system works without email — drafts remain in READY_TO_SEND.
    email_host: str = ""  # e.g. "smtp.gmail.com"
    email_port: int = 587
    email_username: str = ""
    email_password: str = ""  # Use app passwords for Gmail
    email_use_tls: bool = True
    email_from_address: str = ""  # e.g. "you@gmail.com"
    email_from_name: str = "OpportunityOS"
    email_timeout: int = 30  # seconds

    # ── Automation Engine ──────────────────────────────────────────
    automation_enabled: bool = False
    automation_scheduler_interval_minutes: int = 60
    automation_discovery_enabled: bool = True
    automation_matching_enabled: bool = True
    automation_ai_insights_enabled: bool = False  # Requires AI key
    automation_outreach_drafts_enabled: bool = False
    automation_followup_processing_enabled: bool = True
    automation_sources: str = "remotive,arbeitnow,himalayas"  # comma-separated
    automation_min_match_score: int = 60
    automation_max_opportunities_per_run: int = 500
    automation_max_drafts_per_run: int = 20
    automation_dry_run: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()