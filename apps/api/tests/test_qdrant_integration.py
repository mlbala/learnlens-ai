"""Optional live Qdrant Cloud free-tier checks (no paid AI calls).

Skipped unless QDRANT_URL + QDRANT_API_KEY are set and do not look like fixtures.
"""

from __future__ import annotations

import os
import uuid

import pytest
from app.ai.embeddings.fake import FakeEmbeddingAdapter
from app.core.health import check_qdrant
from app.core.settings import Settings, clear_settings_cache
from app.domain.chunking import TextChunk
from app.retrieval.indexer import ChunkIndexer
from app.retrieval.profile import EmbeddingProfile, collection_name_for
from app.retrieval.qdrant_store import QdrantCloudStore
from app.retrieval.query import HybridQueryService
from app.retrieval.scope import AuthorizedScope

pytestmark = pytest.mark.integration


def _qdrant_creds_present() -> bool:
    url = os.getenv("QDRANT_URL", "").strip()
    key = os.getenv("QDRANT_API_KEY", "").strip()
    if not url or not key:
        return False
    if "example.cloud.qdrant.io" in url:
        return False
    return True


@pytest.mark.skipif(not _qdrant_creds_present(), reason="Qdrant Cloud credentials not set")
def test_free_tier_connection_succeeds() -> None:
    clear_settings_cache()
    settings = Settings()
    probe = check_qdrant(settings)
    assert probe.get("ok") is True, probe


@pytest.mark.skipif(not _qdrant_creds_present(), reason="Qdrant Cloud credentials not set")
@pytest.mark.asyncio
async def test_cloud_index_search_delete_with_fake_embeddings() -> None:
    """Upsert/search/delete against a disposable collection using fake embeddings only."""
    clear_settings_cache()
    settings = Settings()
    # Force fake 8-dim profile so we never call paid embedding APIs.
    profile = EmbeddingProfile(
        profile_id=f"fake-phase07-probe-8-v1-{uuid.uuid4().hex[:8]}",
        provider="fake",
        model="fake-embed-v1",
        dimensions=8,
    )
    store = QdrantCloudStore(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    collection = store.ensure_collection(
        profile_id=profile.profile_id,
        dimensions=profile.dimensions,
    )
    assert collection == collection_name_for(profile.profile_id)

    embedder = FakeEmbeddingAdapter(model=profile.model, dimensions=profile.dimensions)
    indexer = ChunkIndexer(store=store, embedder=embedder, profile=profile)
    ws = uuid.uuid4()
    video = uuid.uuid4()
    chunk = TextChunk(
        chunk_id=uuid.uuid4(),
        ordinal=0,
        text="Fixture probe text for Qdrant Cloud hybrid indexing.",
        segment_ids=(uuid.uuid4(),),
        start_ms=None,
        end_ms=None,
        content_hash="probe",
        processing_version="chunk-v1",
        token_estimate=8,
    )
    try:
        result = await indexer.index_chunks(
            chunks=[chunk],
            workspace_id=ws,
            video_id=video,
            source_asset_id=uuid.uuid4(),
            source_revision=1,
            title="probe",
            collection=collection,
        )
        assert result["upserted"] == 1

        query = HybridQueryService(
            store=store,
            embedder=embedder,
            profile=profile,
            settings=settings,
        )
        hits = await query.search_authorized(
            authorized=AuthorizedScope(
                workspace_id=ws,
                scope_kind="video",
                scope_id=video,
                video_ids=(video,),
            ),
            query_text="hybrid indexing probe",
            top_k=5,
            dense_only=True,  # dense-only avoids BM25 model quirks across cluster versions
        )
        assert any(h.chunk_id == chunk.chunk_id for h in hits.hits)

        deleted = indexer.delete_chunk_ids(chunk_ids=[chunk.chunk_id], collection=collection)
        assert deleted == 1
    finally:
        # Best-effort cleanup of the disposable collection.
        try:
            store._client.delete_collection(collection)  # noqa: SLF001
        except Exception:
            pass
    clear_settings_cache()
