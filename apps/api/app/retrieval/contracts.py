"""Retrieval contracts — payload shape matches docs/02 Qdrant collection design."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

DENSE_VECTOR_NAME = "dense"
BM25_VECTOR_NAME = "bm25"
BM25_MODEL = "Qdrant/bm25"


@dataclass(frozen=True, slots=True)
class ChunkIndexRecord:
    """One derived chunk point. Authoritative transcript text stays in Neon."""

    chunk_id: uuid.UUID
    workspace_id: uuid.UUID
    video_id: uuid.UUID
    source_asset_id: uuid.UUID
    source_revision: int
    segment_ids: tuple[uuid.UUID, ...]
    text: str
    dense_vector: list[float]
    start_ms: int | None = None
    end_ms: int | None = None
    title: str = ""
    language: str = "en"
    content_hash: str = ""
    embedding_profile: str = ""
    playlist_ids: tuple[uuid.UUID, ...] = ()
    processing_version: str = ""
    text_preview: str = ""

    def payload(self) -> dict[str, Any]:
        preview = self.text_preview or self.text[:240]
        return {
            "workspace_id": str(self.workspace_id),
            "video_id": str(self.video_id),
            "playlist_ids": [str(p) for p in self.playlist_ids],
            "source_asset_id": str(self.source_asset_id),
            "source_revision": int(self.source_revision),
            "segment_ids": [str(s) for s in self.segment_ids],
            "chunk_id": str(self.chunk_id),
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "title": self.title,
            "language": self.language,
            "content_hash": self.content_hash,
            "embedding_profile": self.embedding_profile,
            "processing_version": self.processing_version,
            "text_preview": preview,
            # Lexical field retained for in-memory BM25; Qdrant uses Document vector.
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk_id: uuid.UUID
    score: float
    payload: dict[str, Any]
    rank: int
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchResult:
    hits: list[SearchHit]
    mode: str  # hybrid | dense_only
    collection: str
    dense_only_flag: bool
    authorized_video_ids: tuple[uuid.UUID, ...]
    workspace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class TenantScopeFilter:
    """Server-built scope only — never accept free-form Qdrant filters from clients."""

    workspace_id: uuid.UUID
    video_ids: tuple[uuid.UUID, ...]


class VectorStore(Protocol):
    """Named dense + BM25/sparse lexical path with optional RRF fusion."""

    def ensure_collection(self, *, profile_id: str, dimensions: int) -> str: ...

    def upsert_chunks(
        self,
        *,
        collection: str,
        profile_id: str,
        dimensions: int,
        records: list[ChunkIndexRecord],
    ) -> int: ...

    def delete_points(
        self,
        *,
        collection: str,
        point_ids: list[uuid.UUID],
    ) -> int: ...

    def delete_by_video(
        self,
        *,
        collection: str,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> int: ...

    def search(
        self,
        *,
        collection: str,
        dimensions: int,
        query_text: str,
        dense_vector: list[float],
        scope: TenantScopeFilter,
        top_k: int,
        dense_only: bool,
        prefetch_limit: int,
    ) -> SearchResult: ...

    def collection_dense_size(self, collection: str) -> int | None: ...

    def count_points(self, collection: str) -> int: ...
