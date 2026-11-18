"""Embedding model adapters (OpenAI / Gemini / fake — no DeepSeek)."""

from app.ai.embeddings.fake import FakeEmbeddingAdapter
from app.ai.embeddings.gemini_adapter import GeminiEmbeddingAdapter
from app.ai.embeddings.openai_adapter import OpenAIEmbeddingAdapter

__all__ = [
    "FakeEmbeddingAdapter",
    "OpenAIEmbeddingAdapter",
    "GeminiEmbeddingAdapter",
]
