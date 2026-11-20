"""Qdrant Cloud hybrid retrieval — derived index only; Neon remains source of truth.

Free-tier expectations (Qdrant Cloud): ~0.5 vCPU / 1 GB RAM / 4 GB disk.
Idle clusters may suspend (~1 week) and eventually delete (~4 weeks). Indexing and
search fail closed with typed errors when the cluster is unreachable; never invent
hits. Dense-only mode is an explicit feature flag (`QDRANT_DENSE_ONLY`), never silent.
"""

from app.retrieval.factory import build_vector_store
from app.retrieval.indexer import ChunkIndexer
from app.retrieval.profile import EmbeddingProfile, active_embedding_profile, collection_name_for
from app.retrieval.query import HybridQueryService

__all__ = [
    "EmbeddingProfile",
    "active_embedding_profile",
    "collection_name_for",
    "build_vector_store",
    "ChunkIndexer",
    "HybridQueryService",
]
