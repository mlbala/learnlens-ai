"""Chunk index upsert / delete — stable IDs, revision-aware, profile-bound."""

from __future__ import annotations

import uuid
from typing import Any

from app.ai.contracts import EmbeddingModel
from app.domain.chunking import TextChunk
from app.retrieval.contracts import ChunkIndexRecord, VectorStore
from app.retrieval.errors import EmbeddingProfileMismatch
from app.retrieval.profile import EmbeddingProfile, verify_vector_dimensions


class ChunkIndexer:
    """Writes derived points into Qdrant/memory; Neon remains source of truth."""

    def __init__(
        self,
        *,
        store: VectorStore,
        embedder: EmbeddingModel,
        profile: EmbeddingProfile,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._profile = profile

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile

    def ensure_collection(self) -> str:
        return self._store.ensure_collection(
            profile_id=self._profile.profile_id,
            dimensions=self._profile.dimensions,
        )

    async def index_chunks(
        self,
        *,
        chunks: list[TextChunk],
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        source_asset_id: uuid.UUID,
        source_revision: int,
        title: str = "",
        language: str = "en",
        playlist_ids: tuple[uuid.UUID, ...] = (),
        collection: str | None = None,
    ) -> dict[str, Any]:
        if not chunks:
            return {
                "collection": collection or self.ensure_collection(),
                "upserted": 0,
                "embedding_profile": self._profile.profile_id,
            }

        coll = collection or self.ensure_collection()
        existing_size = self._store.collection_dense_size(coll)
        if existing_size is not None and existing_size != self._profile.dimensions:
            raise EmbeddingProfileMismatch(
                "Refusing to index into an incompatible collection; reindex required.",
                expected_profile=self._profile.profile_id,
                expected_dimensions=self._profile.dimensions,
                actual_dimensions=existing_size,
            )

        vectors = await self._embedder.embed_documents([c.text for c in chunks])
        if len(vectors) != len(chunks):
            raise EmbeddingProfileMismatch(
                "Embedding adapter returned the wrong number of vectors.",
                expected_profile=self._profile.profile_id,
                expected_dimensions=self._profile.dimensions,
            )

        records: list[ChunkIndexRecord] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            verified = verify_vector_dimensions(vector, profile=self._profile)
            records.append(
                ChunkIndexRecord(
                    chunk_id=chunk.chunk_id,
                    workspace_id=workspace_id,
                    video_id=video_id,
                    source_asset_id=source_asset_id,
                    source_revision=source_revision,
                    segment_ids=chunk.segment_ids,
                    text=chunk.text,
                    dense_vector=verified,
                    start_ms=chunk.start_ms,
                    end_ms=chunk.end_ms,
                    title=title,
                    language=language,
                    content_hash=chunk.content_hash,
                    embedding_profile=self._profile.profile_id,
                    playlist_ids=playlist_ids,
                    processing_version=chunk.processing_version,
                )
            )

        upserted = self._store.upsert_chunks(
            collection=coll,
            profile_id=self._profile.profile_id,
            dimensions=self._profile.dimensions,
            records=records,
        )
        return {
            "collection": coll,
            "upserted": upserted,
            "embedding_profile": self._profile.profile_id,
            "chunk_ids": [str(c.chunk_id) for c in chunks],
            "source_revision": source_revision,
        }

    def delete_chunk_ids(
        self,
        *,
        chunk_ids: list[uuid.UUID],
        collection: str | None = None,
    ) -> int:
        coll = collection or self.ensure_collection()
        return self._store.delete_points(collection=coll, point_ids=chunk_ids)

    def delete_video_index(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        collection: str | None = None,
    ) -> int:
        coll = collection or self.ensure_collection()
        return self._store.delete_by_video(
            collection=coll,
            workspace_id=workspace_id,
            video_id=video_id,
        )
