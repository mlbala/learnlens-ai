"""Hybrid query service — Neon-authorized scope + Qdrant tenant filters + RRF."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import EmbeddingModel
from app.core.settings import Settings
from app.retrieval.contracts import SearchResult, VectorStore
from app.retrieval.filters import build_tenant_scope
from app.retrieval.profile import EmbeddingProfile, verify_vector_dimensions
from app.retrieval.scope import AuthorizedScope, ScopeKind, resolve_authorized_video_ids


class HybridQueryService:
    def __init__(
        self,
        *,
        store: VectorStore,
        embedder: EmbeddingModel,
        profile: EmbeddingProfile,
        settings: Settings,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._profile = profile
        self._settings = settings

    @property
    def dense_only_enabled(self) -> bool:
        """Explicit feature flag — never a silent fallback."""
        return bool(self._settings.qdrant_dense_only)

    async def search(
        self,
        db: AsyncSession,
        *,
        workspace_id: uuid.UUID,
        query_text: str,
        scope_kind: ScopeKind,
        scope_id: uuid.UUID | None = None,
        top_k: int | None = None,
        client_filter: object = None,
        dense_only: bool | None = None,
    ) -> SearchResult:
        authorized = await resolve_authorized_video_ids(
            db,
            workspace_id=workspace_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            client_filter=client_filter,
        )
        return await self.search_authorized(
            authorized=authorized,
            query_text=query_text,
            top_k=top_k,
            dense_only=dense_only,
        )

    async def search_authorized(
        self,
        *,
        authorized: AuthorizedScope,
        query_text: str,
        top_k: int | None = None,
        dense_only: bool | None = None,
    ) -> SearchResult:
        # Dense-only only when explicitly requested or the deployment flag is on.
        use_dense_only = self.dense_only_enabled if dense_only is None else bool(dense_only)
        limit = top_k if top_k is not None else self._settings.qdrant_top_k
        limit = min(max(int(limit), 1), 50)
        prefetch = min(max(self._settings.qdrant_prefetch_limit, limit), 100)

        collection = self._store.ensure_collection(
            profile_id=self._profile.profile_id,
            dimensions=self._profile.dimensions,
        )
        dense = verify_vector_dimensions(
            await self._embedder.embed_query(query_text),
            profile=self._profile,
        )
        scope = build_tenant_scope(
            workspace_id=authorized.workspace_id,
            video_ids=authorized.video_ids,
        )
        return self._store.search(
            collection=collection,
            dimensions=self._profile.dimensions,
            query_text=query_text,
            dense_vector=dense,
            scope=scope,
            top_k=limit,
            dense_only=use_dense_only,
            prefetch_limit=prefetch,
        )

    def result_telemetry(self, result: SearchResult) -> dict[str, Any]:
        """Candidate IDs/scores without raw transcript content."""
        return {
            "mode": result.mode,
            "dense_only_flag": result.dense_only_flag,
            "collection": result.collection,
            "workspace_id": str(result.workspace_id),
            "authorized_video_count": len(result.authorized_video_ids),
            "hits": [
                {
                    "chunk_id": str(h.chunk_id),
                    "score": h.score,
                    "rank": h.rank,
                    "sources": list(h.sources),
                    "video_id": h.payload.get("video_id"),
                    "source_revision": h.payload.get("source_revision"),
                }
                for h in result.hits
            ],
        }
