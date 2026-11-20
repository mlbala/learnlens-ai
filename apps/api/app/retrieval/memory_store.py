"""In-memory vector store — offline fake for CI; mirrors hybrid dense + BM25 + RRF."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.retrieval.contracts import (
    ChunkIndexRecord,
    SearchHit,
    SearchResult,
    TenantScopeFilter,
)
from app.retrieval.errors import EmbeddingProfileMismatch, VectorStoreConfigurationError
from app.retrieval.filters import payload_matches_scope
from app.retrieval.profile import collection_name_for
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.sparse_bm25 import Bm25Index


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


@dataclass
class _Collection:
    profile_id: str
    dimensions: int
    points: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    bm25: Bm25Index = field(default_factory=Bm25Index)


class InMemoryVectorStore:
    """Deterministic hybrid store used when `QDRANT_VECTOR_STORE=memory`."""

    def __init__(self) -> None:
        self._collections: dict[str, _Collection] = {}

    def ensure_collection(self, *, profile_id: str, dimensions: int) -> str:
        if dimensions <= 0:
            raise VectorStoreConfigurationError(
                "dimensions must be positive",
                details={"dimensions": dimensions},
            )
        name = collection_name_for(profile_id)
        existing = self._collections.get(name)
        if existing is None:
            self._collections[name] = _Collection(profile_id=profile_id, dimensions=dimensions)
            return name
        if existing.dimensions != dimensions or existing.profile_id != profile_id:
            raise EmbeddingProfileMismatch(
                "Cannot reuse in-memory collection with a different embedding profile.",
                expected_profile=profile_id,
                actual_profile=existing.profile_id,
                expected_dimensions=dimensions,
                actual_dimensions=existing.dimensions,
            )
        return name

    def collection_dense_size(self, collection: str) -> int | None:
        col = self._collections.get(collection)
        return None if col is None else col.dimensions

    def count_points(self, collection: str) -> int:
        col = self._collections.get(collection)
        return 0 if col is None else len(col.points)

    def upsert_chunks(
        self,
        *,
        collection: str,
        profile_id: str,
        dimensions: int,
        records: list[ChunkIndexRecord],
    ) -> int:
        col = self._require(collection)
        if col.dimensions != dimensions:
            raise EmbeddingProfileMismatch(
                "Collection dense size does not match upsert dimensions.",
                expected_profile=profile_id,
                expected_dimensions=dimensions,
                actual_dimensions=col.dimensions,
            )
        if col.profile_id != profile_id:
            raise EmbeddingProfileMismatch(
                "Collection profile mismatch on upsert.",
                expected_profile=profile_id,
                actual_profile=col.profile_id,
            )
        for record in records:
            if len(record.dense_vector) != dimensions:
                raise EmbeddingProfileMismatch(
                    "Record dense vector has wrong dimensions.",
                    expected_profile=profile_id,
                    expected_dimensions=dimensions,
                    actual_dimensions=len(record.dense_vector),
                )
            payload = record.payload()
            col.points[record.chunk_id] = {
                "dense": list(record.dense_vector),
                "payload": payload,
            }
            col.bm25.add(str(record.chunk_id), record.text)
        return len(records)

    def delete_points(
        self,
        *,
        collection: str,
        point_ids: list[uuid.UUID],
    ) -> int:
        col = self._collections.get(collection)
        if col is None:
            return 0
        removed = 0
        for pid in point_ids:
            if pid in col.points:
                del col.points[pid]
                col.bm25.remove(str(pid))
                removed += 1
        return removed

    def delete_by_video(
        self,
        *,
        collection: str,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> int:
        col = self._collections.get(collection)
        if col is None:
            return 0
        to_delete = [
            pid
            for pid, data in col.points.items()
            if data["payload"].get("workspace_id") == str(workspace_id)
            and data["payload"].get("video_id") == str(video_id)
        ]
        return self.delete_points(collection=collection, point_ids=to_delete)

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
    ) -> SearchResult:
        col = self._require(collection)
        if len(dense_vector) != col.dimensions or dimensions != col.dimensions:
            raise EmbeddingProfileMismatch(
                "Query vector dimensions do not match collection.",
                expected_profile=col.profile_id,
                expected_dimensions=col.dimensions,
                actual_dimensions=len(dense_vector),
            )

        candidates = [
            (pid, data)
            for pid, data in col.points.items()
            if payload_matches_scope(data["payload"], scope)
        ]
        dense_ranked = sorted(
            candidates,
            key=lambda item: (-_cosine(dense_vector, item[1]["dense"]), str(item[0])),
        )
        dense_ids = [pid for pid, _ in dense_ranked[:prefetch_limit]]

        mode = "dense_only" if dense_only else "hybrid"
        fused: list[tuple[uuid.UUID, float, tuple[str, ...]]]
        if dense_only:
            fused = [
                (pid, float(len(dense_ids) - i), ("dense",))
                for i, pid in enumerate(dense_ids[:top_k])
            ]
        else:
            lexical_ids = [
                uuid.UUID(doc_id)
                for doc_id in col.bm25.ranked(
                    query_text,
                    [str(pid) for pid, _ in candidates],
                    limit=prefetch_limit,
                )
            ]
            fused = reciprocal_rank_fusion(
                [dense_ids, lexical_ids],
                sources=("dense", "bm25"),
                limit=top_k,
            )

        hits: list[SearchHit] = []
        for rank, (point_id, score, sources) in enumerate(fused):
            data = col.points.get(point_id)
            if data is None:
                continue
            hits.append(
                SearchHit(
                    chunk_id=point_id,
                    score=float(score),
                    payload=dict(data["payload"]),
                    rank=rank,
                    sources=sources,
                )
            )
        return SearchResult(
            hits=hits,
            mode=mode,
            collection=collection,
            dense_only_flag=dense_only,
            authorized_video_ids=scope.video_ids,
            workspace_id=scope.workspace_id,
        )

    def _require(self, collection: str) -> _Collection:
        col = self._collections.get(collection)
        if col is None:
            raise VectorStoreConfigurationError(
                f"Collection '{collection}' does not exist.",
                details={"collection": collection},
            )
        return col
