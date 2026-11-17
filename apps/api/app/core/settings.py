"""Application settings — Neon, Qdrant Cloud, Redis, CORS (no paid AI calls)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# settings.py → core → app → api → apps → repo root
_API_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Environment-backed settings. Secrets stay out of logs and source control."""

    model_config = SettingsConfigDict(
        # Absolute paths: avoid CWD-relative ../../.env resolving outside the repo.
        env_file=(
            str(_REPO_ROOT / ".env"),
            str(_API_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "learnlens-api"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Neon Postgres (cloud) — required for readiness; no local Postgres.
    database_url: str = Field(default="", alias="DATABASE_URL")

    # Qdrant Cloud — required for readiness; do not run Qdrant in Docker.
    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    # Optional local Redis (Compose profile) or cloud Redis URL.
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    # Exact-origin allowlist (comma-separated). No wildcards.
    cors_origins: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    # Providers default to fake — never call paid APIs from scaffolding.
    ai_chat_provider: str = Field(default="fake", alias="AI_CHAT_PROVIDER")
    ai_embed_provider: str = Field(default="fake", alias="AI_EMBED_PROVIDER")

    @field_validator("database_url", "qdrant_url", "qdrant_api_key", mode="before")
    @classmethod
    def _strip_optional_str(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    def cors_origin_list(self) -> list[str]:
        """Return exact CORS origins (empty entries dropped)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear settings cache (tests / process reloads)."""
    get_settings.cache_clear()
