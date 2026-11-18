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
    ai_chat_model: str = Field(default="fake-chat-v1", alias="AI_CHAT_MODEL")
    ai_embed_provider: str = Field(default="fake", alias="AI_EMBED_PROVIDER")
    ai_embed_model: str = Field(default="fake-embed-v1", alias="AI_EMBED_MODEL")
    # Fake-only default dimension. Real profiles must set verified vendor dimensions.
    ai_embed_dimensions: int = Field(default=64, alias="AI_EMBED_DIMENSIONS")
    ai_request_timeout_seconds: int = Field(default=45, alias="AI_REQUEST_TIMEOUT_SECONDS")
    ai_max_output_tokens: int = Field(default=1800, alias="AI_MAX_OUTPUT_TOKENS")
    ai_max_input_characters: int = Field(default=120_000, alias="AI_MAX_INPUT_CHARACTERS")
    ai_max_retries: int = Field(default=2, alias="AI_MAX_RETRIES")
    # Comma-separated allowlists (env-driven; do not hardcode obsolete catalog IDs).
    ai_chat_provider_allowlist: str = Field(
        default="fake,openai,gemini,deepseek",
        alias="AI_CHAT_PROVIDER_ALLOWLIST",
    )
    ai_chat_model_allowlist: str = Field(
        default="fake-chat-v1",
        alias="AI_CHAT_MODEL_ALLOWLIST",
    )
    ai_embed_provider_allowlist: str = Field(
        default="fake,openai,gemini",
        alias="AI_EMBED_PROVIDER_ALLOWLIST",
    )
    ai_embed_model_allowlist: str = Field(
        default="fake-embed-v1",
        alias="AI_EMBED_MODEL_ALLOWLIST",
    )
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        alias="DEEPSEEK_BASE_URL",
    )

    # Auth / sessions (phase 02). Prefer unpooled Neon URL for Alembic DDL.
    database_url_unpooled: str = Field(default="", alias="DATABASE_URL_UNPOOLED")
    session_secret: str = Field(default="dev-only-change-me", alias="SESSION_SECRET")
    access_token_ttl_seconds: int = Field(default=900, alias="ACCESS_TOKEN_TTL_SECONDS")
    refresh_token_ttl_seconds: int = Field(
        default=60 * 60 * 24 * 14, alias="REFRESH_TOKEN_TTL_SECONDS"
    )
    cookie_secure: bool | None = Field(default=None, alias="COOKIE_SECURE")
    cookie_samesite: str = Field(default="lax", alias="COOKIE_SAMESITE")
    access_cookie_name: str = Field(default="ll_access", alias="ACCESS_COOKIE_NAME")
    refresh_cookie_name: str = Field(default="ll_refresh", alias="REFRESH_COOKIE_NAME")
    csrf_cookie_name: str = Field(default="ll_csrf", alias="CSRF_COOKIE_NAME")
    auth_rate_limit_per_minute: int = Field(default=20, alias="AUTH_RATE_LIMIT_PER_MINUTE")
    # Never enable in production — reserved for offline tests only.
    allow_test_seed: bool = Field(default=False, alias="ALLOW_TEST_SEED")

    @field_validator(
        "database_url",
        "database_url_unpooled",
        "qdrant_url",
        "qdrant_api_key",
        "session_secret",
        "openai_api_key",
        "gemini_api_key",
        "deepseek_api_key",
        "ai_chat_model",
        "ai_embed_model",
        "deepseek_base_url",
        mode="before",
    )
    @classmethod
    def _strip_optional_str(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    def key_configured(self, provider: str) -> bool:
        """Whether a non-empty API key is present for the named provider (fake always true)."""
        name = provider.strip().lower()
        if name == "fake":
            return True
        if name == "openai":
            return bool(self.openai_api_key)
        if name == "gemini":
            return bool(self.gemini_api_key)
        if name == "deepseek":
            return bool(self.deepseek_api_key)
        return False

    @field_validator("cookie_secure", mode="before")
    @classmethod
    def _empty_cookie_secure(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return value

    def cors_origin_list(self) -> list[str]:
        """Return exact CORS origins (empty entries dropped)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def migration_database_url(self) -> str:
        """DDL prefers the direct (unpooled) Neon connection."""
        return self.database_url_unpooled or self.database_url

    def is_production_like(self) -> bool:
        return self.environment.lower() in {"production", "staging", "prod"}



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear settings cache (tests / process reloads)."""
    get_settings.cache_clear()
