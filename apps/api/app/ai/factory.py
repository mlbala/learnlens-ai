"""Independent text + embedding provider factories — no silent paid fallback."""

from __future__ import annotations

from app.ai.allowlist import assert_chat_selection, assert_embed_selection
from app.ai.contracts import EmbeddingModel, TextModel
from app.ai.embeddings import FakeEmbeddingAdapter, GeminiEmbeddingAdapter, OpenAIEmbeddingAdapter
from app.ai.errors import ProviderConfigurationError, ProviderNotSupported
from app.ai.text import DeepSeekTextAdapter, FakeTextAdapter, GeminiTextAdapter, OpenAITextAdapter
from app.core.settings import Settings


def build_text_model(settings: Settings, *, guard: bool = True) -> TextModel:
    """
    Build a chat TextModel. By default wraps with GuardedTextModel so every
    generate_structured call gets evidence sanitization + OutputPolicy.
    """
    # Lazy import avoids circular: ai_guardrails -> ai.contracts -> ai.__init__ -> factory.
    from app.core.policies.ai_guardrails import GuardedTextModel

    provider, model = assert_chat_selection(settings)
    retries = settings.ai_max_retries

    if provider == "fake":
        inner: TextModel = FakeTextAdapter(model=model)
    elif provider == "openai":
        if not settings.openai_api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is not configured.",
                provider=provider,
                details={"error_kind": "missing_key"},
            )
        inner = OpenAITextAdapter(
            api_key=settings.openai_api_key,
            model=model,
            max_retries=retries,
        )
    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is not configured.",
                provider=provider,
                details={"error_kind": "missing_key"},
            )
        inner = GeminiTextAdapter(
            api_key=settings.gemini_api_key,
            model=model,
            max_retries=retries,
        )
    elif provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ProviderConfigurationError(
                "DEEPSEEK_API_KEY is not configured.",
                provider=provider,
                details={"error_kind": "missing_key"},
            )
        inner = DeepSeekTextAdapter(
            api_key=settings.deepseek_api_key,
            model=model,
            base_url=settings.deepseek_base_url,
            max_retries=retries,
        )
    else:
        raise ProviderNotSupported(
            f"Chat provider '{provider}' is not implemented.",
            provider=provider,
        )

    if not guard:
        return inner
    return GuardedTextModel(
        inner,
        max_input_characters=settings.ai_max_input_characters,
    )


def build_embedding_model(settings: Settings) -> EmbeddingModel:
    provider, model = assert_embed_selection(settings)
    dims = settings.ai_embed_dimensions
    retries = settings.ai_max_retries

    if provider == "fake":
        return FakeEmbeddingAdapter(model=model, dimensions=dims)

    if provider == "openai":
        if not settings.openai_api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is not configured.",
                provider=provider,
                details={"error_kind": "missing_key"},
            )
        return OpenAIEmbeddingAdapter(
            api_key=settings.openai_api_key,
            model=model,
            dimensions=dims,
            max_retries=retries,
        )

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is not configured.",
                provider=provider,
                details={"error_kind": "missing_key"},
            )
        return GeminiEmbeddingAdapter(
            api_key=settings.gemini_api_key,
            model=model,
            dimensions=dims,
            max_retries=retries,
        )

    # Explicit refuse — never invent a DeepSeek embedding path or fall back to another vendor.
    raise ProviderNotSupported(
        f"Embedding provider '{provider}' is not implemented.",
        provider=provider,
        details={"error_kind": "embeddings_not_supported"},
    )


def provider_settings_snapshot(settings: Settings) -> dict:
    """Public settings payload — names, capabilities, key presence; never secrets."""
    chat_provider = settings.ai_chat_provider.strip().lower()
    embed_provider = settings.ai_embed_provider.strip().lower()
    chat_caps = _chat_caps(chat_provider)
    embed_caps = _embed_caps(embed_provider)
    from app.ai.allowlist import (
        chat_model_allowlist,
        chat_provider_allowlist,
        embed_model_allowlist,
        embed_provider_allowlist,
        embedding_profile_id,
    )

    profile = embedding_profile_id(
        embed_provider,
        settings.ai_embed_model,
        settings.ai_embed_dimensions,
    )
    return {
        "chat": {
            "provider": chat_provider,
            "model": settings.ai_chat_model,
            "key_configured": settings.key_configured(chat_provider),
            "capabilities": chat_caps,
            "allowlisted_providers": sorted(chat_provider_allowlist(settings)),
            "allowlisted_models": sorted(chat_model_allowlist(settings)),
        },
        "embeddings": {
            "provider": embed_provider,
            "model": settings.ai_embed_model,
            "dimensions": settings.ai_embed_dimensions,
            "profile_id": profile,
            "key_configured": settings.key_configured(embed_provider),
            "capabilities": embed_caps,
            "allowlisted_providers": sorted(embed_provider_allowlist(settings)),
            "allowlisted_models": sorted(embed_model_allowlist(settings)),
            "deepseek_embeddings_supported": False,
        },
        "limits": {
            "request_timeout_seconds": settings.ai_request_timeout_seconds,
            "max_output_tokens": settings.ai_max_output_tokens,
            "max_input_characters": settings.ai_max_input_characters,
            "max_retries": settings.ai_max_retries,
        },
    }


def _chat_caps(provider: str) -> dict:
    defaults = {
        "fake": ModelCaps(True, False, False, False, 32_000),
        "openai": ModelCaps(True, True, False, False, 128_000),
        "gemini": ModelCaps(True, True, False, False, 128_000),
        "deepseek": ModelCaps(False, True, False, False, 64_000),
    }
    caps = defaults.get(provider, ModelCaps(False, False, False, False, 0))
    return caps.as_dict()


def _embed_caps(provider: str) -> dict:
    defaults = {
        "fake": ModelCaps(False, False, False, True, 8_192),
        "openai": ModelCaps(False, False, False, True, 8_192),
        "gemini": ModelCaps(False, False, False, True, 8_192),
    }
    caps = defaults.get(provider, ModelCaps(False, False, False, False, 0))
    return caps.as_dict()


class ModelCaps:
    def __init__(
        self,
        supports_json_schema: bool,
        supports_stream: bool,
        supports_vision: bool,
        supports_batch: bool,
        max_context_tokens: int,
    ) -> None:
        self.supports_json_schema = supports_json_schema
        self.supports_stream = supports_stream
        self.supports_vision = supports_vision
        self.supports_batch = supports_batch
        self.max_context_tokens = max_context_tokens

    def as_dict(self) -> dict:
        return {
            "supports_json_schema": self.supports_json_schema,
            "supports_stream": self.supports_stream,
            "supports_vision": self.supports_vision,
            "supports_batch": self.supports_batch,
            "max_context_tokens": self.max_context_tokens,
        }
