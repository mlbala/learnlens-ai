"""Application settings skeleton (no live cloud clients in phase 00)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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

    # Providers default to fake — never call paid APIs from scaffolding.
    ai_chat_provider: str = Field(default="fake", alias="AI_CHAT_PROVIDER")
    ai_embed_provider: str = Field(default="fake", alias="AI_EMBED_PROVIDER")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
