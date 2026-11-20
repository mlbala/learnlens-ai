"""API health + CORS + request-ID tests (offline; probes mocked)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from app.core.settings import Settings, clear_settings_cache
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    clear_settings_cache()
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AI_CHAT_PROVIDER", "fake")
    monkeypatch.setenv("AI_EMBED_PROVIDER", "fake")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.neon.tech/neondb")
    monkeypatch.setenv("QDRANT_URL", "https://example.cloud.qdrant.io")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key")
    clear_settings_cache()
    return Settings(_env_file=None)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
    clear_settings_cache()


def test_health_live_ok(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["request_id"]
    assert response.headers.get("X-Request-ID") == body["request_id"]


def test_health_live_echoes_incoming_request_id(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "fixed-id-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "fixed-id-123"
    assert response.json()["request_id"] == "fixed-id-123"


def test_health_ready_ok_when_probes_succeed(client: TestClient) -> None:
    neon_ok: dict[str, Any] = {"ok": True}
    qdrant_ok: dict[str, Any] = {"ok": True}
    redis_ok: dict[str, Any] = {"ok": True, "skipped": True}
    with (
        patch("app.api.v1.health.check_neon", new=AsyncMock(return_value=neon_ok)),
        patch("app.api.v1.health.check_qdrant", return_value=qdrant_ok),
        patch("app.api.v1.health.check_redis", return_value=redis_ok),
    ):
        response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["neon"]["ok"] is True
    assert body["checks"]["qdrant"]["ok"] is True
    assert "redis" in body["checks"]
    assert "worker_metrics" in body


def test_health_ready_503_when_neon_fails(client: TestClient) -> None:
    neon_bad: dict[str, Any] = {"ok": False, "error": "TimeoutError"}
    qdrant_ok: dict[str, Any] = {"ok": True}
    redis_ok: dict[str, Any] = {"ok": True, "skipped": True}
    with (
        patch("app.api.v1.health.check_neon", new=AsyncMock(return_value=neon_bad)),
        patch("app.api.v1.health.check_qdrant", return_value=qdrant_ok),
        patch("app.api.v1.health.check_redis", return_value=redis_ok),
    ):
        response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["neon"]["ok"] is False


def test_cors_allows_exact_origin(client: TestClient) -> None:
    response = client.options(
        "/health/live",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/health/live",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "https://evil.example"


def test_settings_load_cloud_infra_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require",
    )
    monkeypatch.setenv("QDRANT_URL", "https://abc.cloud.qdrant.io")
    monkeypatch.setenv("QDRANT_API_KEY", "qk")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    settings = Settings(_env_file=None)
    assert "neon.tech" in settings.database_url
    assert settings.qdrant_url.startswith("https://")
    assert settings.qdrant_api_key == "qk"
    assert settings.cors_origin_list() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
