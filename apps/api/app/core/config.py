from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Core ─────────────────────────────────────────────────────────
    database_url: str
    environment: str = "development"  # development | test | production
    debug: bool = True  # Must be False in production
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── CORS ──────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # In development: http://localhost:3000,http://localhost:3001
    # In production: set to your actual frontend domain(s)
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

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
    ai_api_url: str = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
    ai_api_key: str = ""  # Empty = AI disabled, system still works
    ai_model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    ai_timeout: int = 60  # seconds
    ai_max_tokens: int = 1024

    # ── Email Delivery ──────────────────────────────────────────────
    # Email is OPTIONAL. When email_host is empty, sending is disabled.
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

    # ── Logging ───────────────────────────────────────────────────
    log_level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()