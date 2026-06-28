"""Application configuration, loaded from environment / .env via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Tech Fest Registration API"
    environment: str = "development"

    # Secrets — override in .env / real environment for production.
    jwt_secret: str = "dev-jwt-secret-change-me"
    ticket_secret: str = "dev-ticket-secret-change-me"
    payment_webhook_secret: str = "dev-webhook-secret-change-me"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h

    # Argon2id parameters (memory-hard). Defaults aligned with SCALE.md (m = 46 MiB).
    argon2_time_cost: int = 1
    argon2_memory_cost: int = 47104  # KiB == 46 MiB
    argon2_parallelism: int = 1

    # Spike protection: max concurrent password hashes (the SCALE.md bounded pool).
    hash_concurrency: int = 3

    # Event configuration
    event_name: str = "TechFest 2026"
    capacity: int = 500
    ticket_price: int = 50000  # paise (== 500.00 INR)
    currency: str = "INR"

    # Rate limits (slowapi syntax, e.g. "30/minute"). Generous enough not to impede
    # normal testing, low enough to blunt scripted abuse.
    rate_limit_register: str = "30/minute"
    rate_limit_login: str = "60/minute"

    # Database
    database_url: str = "sqlite:///./techfest.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
