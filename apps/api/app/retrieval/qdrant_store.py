"""Qdrant Cloud store — dense named vector + BM25 Document sparse path with RRF."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from app.retrieval.contracts import (
    BM25_MODEL,
    BM25_VECTOR_NAME,
    DENSE_VECTOR_NAME,
    ChunkIndexRecord,
    SearchHit,
    SearchResult,
    TenantScopeFilter,
)
from app.retrieval.errors import (
    EmbeddingProfileMismatch,
    VectorStoreConfigurationError,
    VectorStoreUnavailable,
)
from app.retrieval.profile import collection_name_for

logger = logging.getLogger("learnlens.retrieval.qdrant")


class QdrantCloudStore:
    """Connects exclusively via QDRANT_URL + QDRANT_API_KEY (no local Docker Qdrant)."""

    def __init__(self, *, url: str, api_key: str, timeout: float = 30.0) -> None:
        if not url or not api_key:
            raise VectorStoreConfigurationError(
                "QDRANT_URL and QDRANT_API_KEY are required for the qdrant backend.",
            )
        self._url = url.rstrip("/")
        try:
            self._client = QdrantClient(
                url=self._url,
                api_key=api_key,
                timeout=timeout,
                check_compatibility=False,
            )
        except Exception as exc:
            raise VectorStoreUnavailable(
                "Failed to initialize Qdrant Cloud client.",
                details={"error_type": type(exc).__name__},
            ) from exc

    def ensure_collection(self, *, profile_id: str, dimensions: int) -> str:
        name = collection_name_for(profile_id)
        try:
            exists = self._client.collection_exists(name)
            if exists:
                size = self.collection_dense_size(name)
                if size is not None and size != dimensions:
                    raise EmbeddingProfileMismatch(
                        (
                            f"Existing collection '{name}' has dense size {size}; "
                            f"profile requires {dimensions}. Reindex into a new collection."
                        ),
                        expected_profile=profile_id,
                        expected_dimensions=dimensions,
                        actual_dimensions=size,
                    )
                return name

            self._client.create_collection(
                collection_name=name,
                vectors_config={
                    DENSE_VECTOR_NAME: models.VectorParams(
                        size=dimensions,
                        distance=models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    BM25_VECTOR_NAME: models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    ),
                },
            )
            # Tenant / scope payload indexes (keyword) for filtered search.
            for field_name in ("workspace_id", "video_id", "embedding_profile", "chunk_id"):
                self._client.create_payload_index(
                    collection_name=name,
                    field_name=field_name,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            return name
        except EmbeddingProfileMismatch:
            raise
        except Exception as exc:
            logger.warning(
                "qdrant_ensure_collection_failed",
                extra={"error_type": type(exc).__name__, "collection": name},
            )
            raise VectorStoreUnavailable(
                "Qdrant Cloud collection ensure failed (cluster may be suspended).",
                details={"error_type": type(exc).__name__, "collection": name},
            ) from exc

    def collection_dense_size(self, collection: str) -> int | None:
        try:
            info = self._client.get_collection(collection)
        except Exception:
            return None
        vectors = info.config.params.vectors
        if isinstance(vectors, dict):
            dense = vectors.get(DENSE_VECTOR_NAME)
            if dense is not None and getattr(dense, "size", None) is not None:
                return int(dense.size)
            return None
        if vectors is not None and getattr(vectors, "size", None) is not None:
            return int(vectors.size)
        return None

    def count_points(self, collection: str) -> int:
        try:
            result = self._client.count(collection_name=collection, exact=True)
            return int(result.count)
        except Exception as exc:
            raise VectorStoreUnavailable(
                "Qdrant Cloud count failed.",
                details={"error_type": type(exc).__name__},
            ) from exc

    def upsert_chunks(
        self,
        *,
        collection: str,
        profile_id: str,
        dimensions: int,
        records: list[ChunkIndexRecord],
    ) -> int:
        if not records:
            return 0
        size = self.collection_dense_size(collection)
        if size is not None and size != dimensions:
            raise EmbeddingProfileMismatch(
                "Refusing to upsert into a collection with incompatible dimensions.",
                expected_profile=profile_id,
                expected_dimensions=dimensions,
                actual_dimensions=size,
            )
        points: list[models.PointStruct] = []
        for record in records:
            if len(record.dense_vector) != dimensions:
                raise EmbeddingProfileMismatch(
                    "Record dense vector has wrong dimensions.",
                    expected_profile=profile_id,
                    expected_dimensions=dimensions,
                    actual_dimensions=len(record.dense_vector),
                )
            points.append(
                models.PointStruct(
                    id=str(record.chunk_id),
                    vector={
                        DENSE_VECTOR_NAME: record.dense_vector,
                        BM25_VECTOR_NAME: models.Document(
                            text=record.text,
                            model=BM25_MODEL,
                        ),
                    },
                    payload=record.payload(),
                )
            )
        try:
            self._client.upsert(collection_name=collection, points=points, wait=True)
            return len(points)
        except EmbeddingProfileMismatch:
            raise
        except Exception as exc:
            logger.warning(
                "qdrant_upsert_failed",
                extra={"error_type": type(exc).__name__, "collection": collection},
            )
            raise VectorStoreUnavailable(
                "Qdrant Cloud upsert failed.",
                details={"error_type": type(exc).__name__},
            ) from exc

    def delete_points(
        self,
        *,
        collection: str,
        point_ids: list[uuid.UUID],
    ) -> int:
        if not point_ids:
            return 0
        try:
            self._client.delete(
                collection_name=collection,
                points_selector=models.PointIdsList(
                    points=[str(pid) for pid in point_ids],
                ),
                wait=True,
            )
            return len(point_ids)
        except Exception as exc:
            raise VectorStoreUnavailable(
                "Qdrant Cloud delete failed.",
                details={"error_type": type(exc).__name__},
            ) from exc

    def delete_by_video(
        self,
        *,
        collection: str,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> int:
        try:
            # Count matching points first for testability / observability.
            before = self._client.count(
                collection_name=collection,
                count_filter=_tenant_filter(workspace_id, (video_id,)),
                exact=True,
            )
            self._client.delete(
                collection_name=collection,
                points_selector=models.FilterSelector(
                    filter=_tenant_filter(workspace_id, (video_id,)),
                ),
                wait=True,
            )
            return int(before.count)
        except Exception as exc:
            raise VectorStoreUnavailable(
                "Qdrant Cloud filtered delete failed.",
                details={"error_type": type(exc).__name__},
            ) from exc

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
        if len(dense_vector) != dimensions:
            raise EmbeddingProfileMismatch(
                "Query vector dimensions do not match profile.",
                expected_profile=collection,
                expected_dimensions=dimensions,
                actual_dimensions=len(dense_vector),
            )
        query_filter = _tenant_filter(scope.workspace_id, scope.video_ids)
        try:
            if dense_only:
                response = self._client.query_points(
                    collection_name=collection,
                    query=dense_vector,
                    using=DENSE_VECTOR_NAME,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )
                mode = "dense_only"
                hits = _hits_from_points(response.points, sources=("dense",))
            else:
                response = self._client.query_points(
                    collection_name=collection,
                    prefetch=[
                        models.Prefetch(
                            query=dense_vector,
                            using=DENSE_VECTOR_NAME,
                            filter=query_filter,
                            limit=prefetch_limit,
                        ),
                        models.Prefetch(
                            query=models.Document(text=query_text, model=BM25_MODEL),
                            using=BM25_VECTOR_NAME,
                            filter=query_filter,
                            limit=prefetch_limit,
                        ),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )
                mode = "hybrid"
                hits = _hits_from_points(response.points, sources=("dense", "bm25"))
        except EmbeddingProfileMismatch:
            raise
        except Exception as exc:
            logger.warning(
                "qdrant_search_failed",
                extra={"error_type": type(exc).__name__, "collection": collection},
            )
            raise VectorStoreUnavailable(
                "Qdrant Cloud search failed (check free-tier cluster status).",
                details={"error_type": type(exc).__name__},
            ) from exc

        return SearchResult(
            hits=hits,
            mode=mode,
            collection=collection,
            dense_only_flag=dense_only,
            authorized_video_ids=scope.video_ids,
            workspace_id=scope.workspace_id,
        )


def _tenant_filter(
    workspace_id: uuid.UUID,
    video_ids: tuple[uuid.UUID, ...],
) -> models.Filter:
    """Always require workspace_id + authorized video IDs (MatchValue / MatchAny)."""
    return models.Filter(
        must=[
            models.FieldCondition(
                key="workspace_id",
                match=models.MatchValue(value=str(workspace_id)),
            ),
            models.FieldCondition(
                key="video_id",
                match=models.MatchAny(any=[str(v) for v in video_ids]),
            ),
        ]
    )


def _hits_from_points(
    points: list[Any],
    *,
    sources: tuple[str, ...],
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for rank, point in enumerate(points):
        payload = dict(point.payload or {})
        raw_id = point.id
        try:
            chunk_id = uuid.UUID(str(payload.get("chunk_id") or raw_id))
        except ValueError:
            continue
        hits.append(
            SearchHit(
                chunk_id=chunk_id,
                score=float(point.score or 0.0),
                payload=payload,
                rank=rank,
                sources=sources,
            )
        )
    return hits
