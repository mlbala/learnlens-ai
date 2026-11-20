"""Factory: independent chat/embed selection; no silent paid fallback."""

from __future__ import annotations

import pytest
from app.ai.embeddings.gemini_adapter import GeminiEmbeddingAdapter
from app.ai.embeddings.openai_adapter import OpenAIEmbeddingAdapter
from app.ai.errors import ProviderConfigurationError, ProviderNotSupported
from app.ai.factory import build_embedding_model, build_text_model
from app.ai.text.deepseek_adapter import DeepSeekTextAdapter
from app.core.policies.ai_guardrails import GuardedTextModel
from app.core.settings import Settings, clear_settings_cache


def test_deepseek_chat_plus_gemini_embeddings_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CHAT_PROVIDER", "deepseek")
    monkeypatch.setenv("AI_CHAT_MODEL", "deepseek-fixture-chat")
    monkeypatch.setenv("AI_CHAT_MODEL_ALLOWLIST", "deepseek-fixture-chat,fake-chat-v1")
    monkeypatch.setenv("AI_EMBED_PROVIDER", "gemini")
    monkeypatch.setenv("AI_EMBED_MODEL", "gemini-embed-fixture")
    monkeypatch.setenv("AI_EMBED_MODEL_ALLOWLIST", "gemini-embed-fixture,fake-embed-v1")
    monkeypatch.setenv("AI_EMBED_DIMENSIONS", "768")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-test")
    clear_settings_cache()
    settings = Settings(_env_file=None)

    text = build_text_model(settings)
    embed = build_embedding_model(settings)
    assert isinstance(text, GuardedTextModel)
    assert text.provider == "deepseek"
    assert isinstance(text._inner, DeepSeekTextAdapter)  # noqa: SLF001 — factory guard wrap
    assert isinstance(embed, GeminiEmbeddingAdapter)
    assert embed.dimensions == 768
    assert "768" in embed.profile_id


def test_build_text_model_unguarded_returns_inner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CHAT_PROVIDER", "deepseek")
    monkeypatch.setenv("AI_CHAT_MODEL", "deepseek-fixture-chat")
    monkeypatch.setenv("AI_CHAT_MODEL_ALLOWLIST", "deepseek-fixture-chat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    clear_settings_cache()
    settings = Settings(_env_file=None)
    text = build_text_model(settings, guard=False)
    assert isinstance(text, DeepSeekTextAdapter)


def test_deepseek_chat_plus_openai_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CHAT_PROVIDER", "deepseek")
    monkeypatch.setenv("AI_CHAT_MODEL", "deepseek-fixture-chat")
    monkeypatch.setenv("AI_CHAT_MODEL_ALLOWLIST", "deepseek-fixture-chat")
    monkeypatch.setenv("AI_EMBED_PROVIDER", "openai")
    monkeypatch.setenv("AI_EMBED_MODEL", "openai-embed-fixture")
    monkeypatch.setenv("AI_EMBED_MODEL_ALLOWLIST", "openai-embed-fixture")
    monkeypatch.setenv("AI_EMBED_DIMENSIONS", "1536")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    clear_settings_cache()
    settings = Settings(_env_file=None)

    text = build_text_model(settings)
    embed = build_embedding_model(settings)
    assert text.provider == "deepseek"
    assert isinstance(embed, OpenAIEmbeddingAdapter)


def test_deepseek_embeddings_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_EMBED_PROVIDER", "deepseek")
    monkeypatch.setenv("AI_EMBED_MODEL", "anything")
    monkeypatch.setenv("AI_EMBED_PROVIDER_ALLOWLIST", "fake,openai,gemini,deepseek")
    clear_settings_cache()
    settings = Settings(_env_file=None)
    with pytest.raises(ProviderNotSupported) as excinfo:
        build_embedding_model(settings)
    assert "DeepSeek embeddings" in str(excinfo.value)


def test_missing_key_does_not_fallback_to_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("AI_CHAT_MODEL", "allowlisted-chat")
    monkeypatch.setenv("AI_CHAT_MODEL_ALLOWLIST", "allowlisted-chat")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    clear_settings_cache()
    settings = Settings(_env_file=None)
    with pytest.raises(ProviderConfigurationError):
        build_text_model(settings)


def test_model_not_on_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("AI_CHAT_MODEL", "not-allowlisted")
    monkeypatch.setenv("AI_CHAT_MODEL_ALLOWLIST", "fake-chat-v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    clear_settings_cache()
    settings = Settings(_env_file=None)
    with pytest.raises(ProviderNotSupported):
        build_text_model(settings)
