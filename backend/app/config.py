"""Runtime configuration, loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_stt_model: str = "gpt-4o-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
    openai_vision_model: str = "gpt-4.1"
    openai_chat_model: str = "gpt-4.1-mini"

    # --- External data sources ---
    data_gov_in_api_key: str = ""
    openweather_api_key: str = ""
    nominatim_user_agent: str = "BharatFarms/1.0 (you@example.com)"

    # --- Infra ---
    database_url: str = "sqlite:///./bharatfarms.db"
    cors_allow_origins: str = "*"
    request_timeout_seconds: int = 30
    # Run the in-process daily refresh (APScheduler). Recommended on Render's
    # single web service; set false if you drive refreshes with an external cron.
    enable_scheduler: bool = False
    # Optional shared secret to guard POST /api/admin/refresh.
    admin_token: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        raw = self.cors_allow_origins.strip()
        if raw == "*" or not raw:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
