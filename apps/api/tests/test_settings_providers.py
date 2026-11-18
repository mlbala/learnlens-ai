"""GET /api/v1/settings/providers — authenticated, no secrets."""

from __future__ import annotations

from app.ai.factory import provider_settings_snapshot
from app.core.settings import Settings
from fastapi.testclient import TestClient


def test_settings_providers_requires_auth(client: TestClient) -> None:
    res = client.get("/api/v1/settings/providers")
    assert res.status_code == 401


def test_settings_providers_hides_secrets(client: TestClient) -> None:
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "prov@example.com", "password": "correct-horse"},
    )
    assert reg.status_code == 201, reg.text

    res = client.get("/api/v1/settings/providers")
    assert res.status_code == 200, res.text
    body = res.json()
    blob = str(body).lower()
    assert "api_key" not in blob
    assert "sk-" not in blob

    assert body["chat"]["provider"] == "fake"
    assert body["chat"]["model"] == "fake-chat-v1"
    assert body["chat"]["key_configured"] is True
    assert body["embeddings"]["provider"] == "fake"
    assert body["embeddings"]["dimensions"] == 64
    assert body["embeddings"]["deepseek_embeddings_supported"] is False
    assert "supports_json_schema" in body["chat"]["capabilities"]
    assert body["limits"]["max_retries"] >= 0


def test_snapshot_never_includes_key_material() -> None:
    settings = Settings(
        _env_file=None,
        ai_chat_provider="openai",
        ai_chat_model="allowlisted-chat",
        ai_chat_model_allowlist="allowlisted-chat",
        ai_embed_provider="gemini",
        ai_embed_model="allowlisted-embed",
        ai_embed_model_allowlist="allowlisted-embed",
        ai_embed_dimensions=768,
        openai_api_key="sk-super-secret-value",
        gemini_api_key="gem-super-secret-value",
        deepseek_api_key="ds-super-secret-value",
    )
    snap = provider_settings_snapshot(settings)
    blob = str(snap)
    assert "sk-super-secret-value" not in blob
    assert "gem-super-secret-value" not in blob
    assert "ds-super-secret-value" not in blob
    assert snap["chat"]["key_configured"] is True
    assert snap["embeddings"]["key_configured"] is True
    assert snap["embeddings"]["deepseek_embeddings_supported"] is False
