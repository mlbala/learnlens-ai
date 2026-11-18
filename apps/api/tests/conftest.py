"""Shared offline fixtures — SQLite in-memory DB, no paid providers."""

from __future__ import annotations

from collections.abc import Iterator

import anyio
import pytest
from app.core.rate_limit import configure_auth_rate_limiter
from app.core.settings import Settings, clear_settings_cache
from app.db import models as _models  # noqa: F401 — register metadata
from app.db.base import Base
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    clear_settings_cache()
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("AI_CHAT_PROVIDER", "fake")
    monkeypatch.setenv("AI_CHAT_MODEL", "fake-chat-v1")
    monkeypatch.setenv("AI_EMBED_PROVIDER", "fake")
    monkeypatch.setenv("AI_EMBED_MODEL", "fake-embed-v1")
    monkeypatch.setenv("AI_EMBED_DIMENSIONS", "64")
    monkeypatch.setenv("AI_CHAT_MODEL_ALLOWLIST", "fake-chat-v1")
    monkeypatch.setenv("AI_EMBED_MODEL_ALLOWLIST", "fake-embed-v1")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite://")
    monkeypatch.setenv("QDRANT_URL", "https://example.cloud.qdrant.io")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-not-for-prod")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("ALLOW_TEST_SEED", "true")
    monkeypatch.setenv("AUTH_RATE_LIMIT_PER_MINUTE", "100")
    clear_settings_cache()
    configure_auth_rate_limiter(limit=100, window_seconds=60.0)
    return Settings(_env_file=None)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        engine: AsyncEngine = app.state.engine
        assert engine is not None

        async def _prepare() -> None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        anyio.run(_prepare)
        yield test_client
    clear_settings_cache()

