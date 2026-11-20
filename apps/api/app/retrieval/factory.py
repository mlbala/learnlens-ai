"""Vector store factory — memory for offline tests, Qdrant Cloud otherwise."""

from __future__ import annotations

from app.core.settings import Settings
from app.retrieval.errors import VectorStoreConfigurationError
from app.retrieval.memory_store import InMemoryVectorStore
from app.retrieval.qdrant_store import QdrantCloudStore

# Process-local memory singleton so indexer + query share state in tests.
_MEMORY_STORE: InMemoryVectorStore | None = None


def reset_memory_store() -> None:
    """Clear the shared in-memory store (tests)."""
    global _MEMORY_STORE
    _MEMORY_STORE = None


def build_vector_store(settings: Settings) -> InMemoryVectorStore | QdrantCloudStore:
    backend = settings.qdrant_vector_store.strip().lower()
    if backend == "memory":
        global _MEMORY_STORE
        if _MEMORY_STORE is None:
            _MEMORY_STORE = InMemoryVectorStore()
        return _MEMORY_STORE
    if backend == "qdrant":
        return QdrantCloudStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    raise VectorStoreConfigurationError(
        f"Unsupported QDRANT_VECTOR_STORE '{backend}' (use memory|qdrant).",
        details={"backend": backend},
    )
