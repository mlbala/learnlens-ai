"""Vector store factory — memory for offline tests, Qdrant Cloud otherwise."""

from __future__ import annotations

import hashlib

from app.core.settings import Settings
from app.retrieval.errors import VectorStoreConfigurationError
from app.retrieval.memory_store import InMemoryVectorStore
from app.retrieval.qdrant_store import QdrantCloudStore

# Process-local memory singleton so indexer + query share state in tests.
_MEMORY_STORE: InMemoryVectorStore | None = None
# One Qdrant client per URL and key, so each call reuses an open HTTPS connection
# instead of a new handshake. Keyed by a digest; the key itself is not stored here.
_QDRANT_STORES: dict[tuple[str, str], QdrantCloudStore] = {}


def reset_memory_store() -> None:
    """Clear the shared in-memory store (tests)."""
    global _MEMORY_STORE
    _MEMORY_STORE = None


def reset_qdrant_stores() -> None:
    """Drop cached Qdrant clients (tests)."""
    _QDRANT_STORES.clear()


def build_vector_store(settings: Settings) -> InMemoryVectorStore | QdrantCloudStore:
    backend = settings.qdrant_vector_store.strip().lower()
    if backend == "memory":
        global _MEMORY_STORE
        if _MEMORY_STORE is None:
            _MEMORY_STORE = InMemoryVectorStore()
        return _MEMORY_STORE
    if backend == "qdrant":
        key = (
            settings.qdrant_url,
            hashlib.sha256(settings.qdrant_api_key.encode()).hexdigest(),
        )
        store = _QDRANT_STORES.get(key)
        if store is None:
            store = QdrantCloudStore(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
            )
            _QDRANT_STORES[key] = store
        return store
    raise VectorStoreConfigurationError(
        f"Unsupported QDRANT_VECTOR_STORE '{backend}' (use memory|qdrant).",
        details={"backend": backend},
    )
