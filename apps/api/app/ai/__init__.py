"""AI provider adapters — text (OpenAI/Gemini/DeepSeek/fake) and embeddings (OpenAI/Gemini/fake)."""

from app.ai.contracts import EmbeddingModel, ModelRequest, ModelResult, TextModel
from app.ai.factory import build_embedding_model, build_text_model, provider_settings_snapshot

__all__ = [
    "TextModel",
    "EmbeddingModel",
    "ModelRequest",
    "ModelResult",
    "build_text_model",
    "build_embedding_model",
    "provider_settings_snapshot",
]
