"""Environment-driven settings for the Market Flow service."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    All values may be overridden with environment variables prefixed with
    ``MARKET_FLOW_`` (see ``.env.example``).
    """

    env: str = "development"
    provider: str = "mock"
    log_level: str = "info"

    # TwelveData provider (used when provider="twelvedata").
    twelvedata_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="MARKET_FLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
