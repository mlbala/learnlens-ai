"""Auth session lifecycle tests (offline SQLite)."""

from __future__ import annotations

import pytest
from app.core.security import cookie_secure
from app.core.settings import Settings
from fastapi.testclient import TestClient

from auth_helpers import auth_csrf_headers


def test_register_login_me_logout(client: TestClient) -> None:
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "Alice@Example.com", "password": "correct-horse", "name": "Alice"},
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["workspace"]["id"]
    assert client.cookies.get("ll_access")
    assert client.cookies.get("ll_refresh")
    assert client.cookies.get("ll_csrf")

    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "alice@example.com"

    logout = client.post("/api/v1/auth/logout", headers=auth_csrf_headers(client))
    assert logout.status_code == 204

    me_after = client.get("/api/v1/me")
    assert me_after.status_code == 401


def test_login_rejects_bad_password_without_enumeration(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "password": "correct-horse"},
    )
    client.cookies.clear()

    missing = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "correct-horse"},
    )
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrong-password"},
    )
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["error"]["message"] == wrong.json()["error"]["message"]
    assert missing.json()["error"]["code"] == "INVALID_CREDENTIALS"
    # No secrets in error payload
    assert "password" not in str(missing.json()).lower() or "Invalid email or password" in str(
        missing.json()
    )
    assert "argon" not in str(missing.json()).lower()


def test_refresh_rotates_and_rejects_reuse(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "cara@example.com", "password": "correct-horse"},
    )
    old_refresh = client.cookies.get("ll_refresh")
    assert old_refresh

    rotated = client.post("/api/v1/auth/refresh", headers=auth_csrf_headers(client))
    assert rotated.status_code == 200, rotated.text
    new_refresh = client.cookies.get("ll_refresh")
    assert new_refresh
    assert new_refresh != old_refresh

    # Replay old refresh with matching (new) CSRF should fail session lookup / CSRF bind.
    # httpx2 jars are domain-scoped (testserver.local); overwrite that entry explicitly.
    client.cookies.set("ll_refresh", old_refresh, domain="testserver.local")
    replay = client.post("/api/v1/auth/refresh", headers=auth_csrf_headers(client))
    assert replay.status_code in {401, 403}


def test_logout_without_csrf_rejected(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "dan@example.com", "password": "correct-horse"},
    )
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_me_rejects_anonymous(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_cookie_secure_flag_environment_dependent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-not-for-prod")
    dev = Settings(ENVIRONMENT="development", _env_file=None)
    prod = Settings(ENVIRONMENT="production", _env_file=None)
    forced = Settings(ENVIRONMENT="production", COOKIE_SECURE="false", _env_file=None)
    assert cookie_secure(dev) is False
    assert cookie_secure(prod) is True
    assert cookie_secure(forced) is False
