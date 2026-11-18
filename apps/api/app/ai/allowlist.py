"""Env-driven provider/model allowlists — no hardcoded obsolete model IDs."""

from __future__ import annotations

from app.ai.errors import ProviderNotSupported
from app.core.settings import Settings

# Provider *names* are stable product identifiers (not model catalog IDs).
TEXT_PROVIDERS = frozenset({"fake", "openai", "gemini", "deepseek"})
EMBED_PROVIDERS = frozenset({"fake", "openai", "gemini"})  # no DeepSeek embeddings


def _split_csv(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def chat_provider_allowlist(settings: Settings) -> set[str]:
    configured = _split_csv(settings.ai_chat_provider_allowlist)
    return configured & TEXT_PROVIDERS if configured else set(TEXT_PROVIDERS)


def chat_model_allowlist(settings: Settings) -> set[str]:
    return _split_csv(settings.ai_chat_model_allowlist)


def embed_provider_allowlist(settings: Settings) -> set[str]:
    configured = _split_csv(settings.ai_embed_provider_allowlist)
    return configured & EMBED_PROVIDERS if configured else set(EMBED_PROVIDERS)


def embed_model_allowlist(settings: Settings) -> set[str]:
    return _split_csv(settings.ai_embed_model_allowlist)


def assert_chat_selection(settings: Settings) -> tuple[str, str]:
    provider = settings.ai_chat_provider.strip().lower()
    model = settings.ai_chat_model.strip()
    if provider not in chat_provider_allowlist(settings):
        raise ProviderNotSupported(
            f"Chat provider '{provider}' is not allowlisted.",
            provider=provider,
            details={"error_kind": "provider_not_allowlisted"},
        )
    models = chat_model_allowlist(settings)
    if models and model not in models:
        raise ProviderNotSupported(
            "Chat model is not allowlisted.",
            provider=provider,
            details={"error_kind": "model_not_allowlisted"},
        )
    return provider, model


def assert_embed_selection(settings: Settings) -> tuple[str, str]:
    provider = settings.ai_embed_provider.strip().lower()
    model = settings.ai_embed_model.strip()
    # Fail closed before allowlist: DeepSeek has no embedding adapter (ADR-002).
    if provider == "deepseek":
        raise ProviderNotSupported(
            "DeepSeek embeddings are not supported; choose openai, gemini, or fake.",
            provider=provider,
            details={"error_kind": "embeddings_not_supported"},
        )
    if provider not in embed_provider_allowlist(settings):
        raise ProviderNotSupported(
            f"Embedding provider '{provider}' is not allowlisted.",
            provider=provider,
            details={"error_kind": "provider_not_allowlisted"},
        )
    models = embed_model_allowlist(settings)
    if models and model not in models:
        raise ProviderNotSupported(
            "Embedding model is not allowlisted.",
            provider=provider,
            details={"error_kind": "model_not_allowlisted"},
        )
    return provider, model


def embedding_profile_id(provider: str, model: str, dimensions: int) -> str:
    """Stable profile slug used for collection naming / manifests."""
    safe_model = model.replace("/", "-").replace(" ", "-").lower()
    return f"{provider}-{safe_model}-{dimensions}-v1"
