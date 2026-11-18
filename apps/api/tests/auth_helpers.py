"""Small test helpers for cookie auth."""

from __future__ import annotations

from fastapi.testclient import TestClient


def auth_csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("ll_csrf")
    assert token, "expected ll_csrf cookie after auth"
    return {"X-CSRF-Token": token}
