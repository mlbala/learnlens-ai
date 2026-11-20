"""Phase 07 — fake embedding index/search, tenant isolation, RRF, dimension safety."""

from __future__ import annotations

import uuid

import pytest
from app.ai.embeddings.fake import FakeEmbeddingAdapter
from app.core.settings import Settings, clear_settings_cache
from app.db.base import Base
from app.db.models import Playlist, PlaylistItem, Video
from app.db.session import create_engine, create_session_factory
from app.domain.chunking import TextChunk
from app.retrieval.errors import (
    EmbeddingProfileMismatch,
    InvalidRetrievalFilter,
    UnauthorizedScopeError,
)
from app.retrieval.factory import build_vector_store, reset_memory_store
from app.retrieval.filters import parse_uuid, reject_freeform_filter
from app.retrieval.indexer import ChunkIndexer
from app.retrieval.profile import (
    EmbeddingProfile,
    active_embedding_profile,
    collection_name_for,
    verify_embedding_adapter_dimensions,
    verify_vector_dimensions,
)
from app.retrieval.query import HybridQueryService
from app.retrieval.reindex import plan_embedding_profile_change
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.scope import AuthorizedScope, resolve_authorized_video_ids
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    clear_settings_cache()
    reset_memory_store()
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("AI_EMBED_PROVIDER", "fake")
    monkeypatch.setenv("AI_EMBED_MODEL", "fake-embed-v1")
    monkeypatch.setenv("AI_EMBED_DIMENSIONS", "64")
    monkeypatch.setenv("QDRANT_URL", "https://example.cloud.qdrant.io")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key")
    monkeypatch.setenv("QDRANT_VECTOR_STORE", "memory")
    monkeypatch.setenv("QDRANT_DENSE_ONLY", "false")
    monkeypatch.setenv("QDRANT_TOP_K", "10")
    monkeypatch.setenv("QDRANT_PREFETCH_LIMIT", "40")
    clear_settings_cache()
    return Settings(_env_file=None)


def _chunk(text: str, *segment_ids: uuid.UUID) -> TextChunk:
    segs = segment_ids or (uuid.uuid4(),)
    return TextChunk(
        chunk_id=uuid.uuid5(uuid.NAMESPACE_URL, f"test:{text}:{segs[0]}"),
        ordinal=0,
        text=text,
        segment_ids=tuple(segs),
        start_ms=0,
        end_ms=1_000,
        content_hash="abc",
        processing_version="chunk-v1",
        token_estimate=len(text.split()),
    )


@pytest.mark.asyncio
async def test_fake_embedding_dimension_probe(settings: Settings) -> None:
    profile = active_embedding_profile(settings)
    embedder = FakeEmbeddingAdapter(model=profile.model, dimensions=profile.dimensions)
    vector = await verify_embedding_adapter_dimensions(embedder, profile=profile)
    assert len(vector) == 64


def test_collection_name_includes_profile_slug(settings: Settings) -> None:
    profile = active_embedding_profile(settings)
    name = collection_name_for(profile.profile_id)
    assert name.startswith("learnlens_chunks_")
    assert "fake-embed-v1" in name or "64" in name


def test_wrong_dimensions_rejected(settings: Settings) -> None:
    profile = active_embedding_profile(settings)
    with pytest.raises(EmbeddingProfileMismatch):
        verify_vector_dimensions([0.1, 0.2], profile=profile)


def test_rrf_fusion_contract() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    fused = reciprocal_rank_fusion(
        [[a, b], [b, c]],
        sources=("dense", "bm25"),
        limit=3,
    )
    ids = [item[0] for item in fused]
    assert b in ids  # appears in both lists → boosted
    assert fused[0][0] == b
    assert "dense" in fused[0][2] and "bm25" in fused[0][2]


def test_reject_freeform_filter() -> None:
    with pytest.raises(InvalidRetrievalFilter):
        reject_freeform_filter({"must": [{"key": "workspace_id"}]})
    with pytest.raises(InvalidRetrievalFilter):
        parse_uuid("not-a-uuid", field_name="workspace_id")


def test_reindex_plan_never_mixes_dimensions() -> None:
    active = EmbeddingProfile(
        profile_id="fake-fake-embed-v1-64-v1",
        provider="fake",
        model="fake-embed-v1",
        dimensions=64,
    )
    target = EmbeddingProfile(
        profile_id="fake-fake-embed-v1-128-v1",
        provider="fake",
        model="fake-embed-v1",
        dimensions=128,
    )
    plan = plan_embedding_profile_change(active=active, target=target)
    assert plan.requires_reindex is True
    assert plan.active_collection != plan.target_collection


@pytest.mark.asyncio
async def test_index_search_delete_and_hybrid_fusion(settings: Settings) -> None:
    store = build_vector_store(settings)
    profile = active_embedding_profile(settings)
    embedder = FakeEmbeddingAdapter(model=profile.model, dimensions=profile.dimensions)
    indexer = ChunkIndexer(store=store, embedder=embedder, profile=profile)

    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()
    video_a = uuid.uuid4()
    video_b = uuid.uuid4()
    asset = uuid.uuid4()

    chunk_listen = _chunk(
        "Active listening requires attention and clarification questions.",
        uuid.uuid4(),
    )
    chunk_code = _chunk(
        "Python list comprehensions transform sequences efficiently.",
        uuid.uuid4(),
    )
    chunk_other_tenant = _chunk(
        "Active listening requires attention and clarification questions.",
        uuid.uuid4(),
    )

    await indexer.index_chunks(
        chunks=[chunk_listen, chunk_code],
        workspace_id=ws_a,
        video_id=video_a,
        source_asset_id=asset,
        source_revision=1,
        title="Communication",
    )
    await indexer.index_chunks(
        chunks=[chunk_other_tenant],
        workspace_id=ws_b,
        video_id=video_b,
        source_asset_id=uuid.uuid4(),
        source_revision=1,
        title="Other workspace",
    )

    query = HybridQueryService(
        store=store,
        embedder=embedder,
        profile=profile,
        settings=settings,
    )
    result = await query.search_authorized(
        authorized=AuthorizedScope(
            workspace_id=ws_a,
            scope_kind="video",
            scope_id=video_a,
            video_ids=(video_a,),
        ),
        query_text="clarification questions listening",
        top_k=5,
        dense_only=False,
    )
    assert result.mode == "hybrid"
    assert result.dense_only_flag is False
    assert result.hits
    hit_videos = {h.payload.get("video_id") for h in result.hits}
    assert str(video_a) in hit_videos
    assert str(video_b) not in hit_videos
    assert all(h.payload.get("workspace_id") == str(ws_a) for h in result.hits)

    # Lexical path should surface the listening chunk for exact tokens.
    assert any(h.chunk_id == chunk_listen.chunk_id for h in result.hits)

    deleted = indexer.delete_chunk_ids(chunk_ids=[chunk_listen.chunk_id])
    assert deleted == 1
    after = await query.search_authorized(
        authorized=AuthorizedScope(
            workspace_id=ws_a,
            scope_kind="video",
            scope_id=video_a,
            video_ids=(video_a,),
        ),
        query_text="clarification questions listening",
        top_k=5,
    )
    assert all(h.chunk_id != chunk_listen.chunk_id for h in after.hits)

    removed = indexer.delete_video_index(workspace_id=ws_a, video_id=video_a)
    assert removed >= 1
    empty = await query.search_authorized(
        authorized=AuthorizedScope(
            workspace_id=ws_a,
            scope_kind="video",
            scope_id=video_a,
            video_ids=(video_a,),
        ),
        query_text="list comprehensions",
        top_k=5,
    )
    assert empty.hits == []


@pytest.mark.asyncio
async def test_dense_only_is_explicit_flag(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QDRANT_DENSE_ONLY", "true")
    clear_settings_cache()
    reset_memory_store()
    flagged = Settings(_env_file=None)
    store = build_vector_store(flagged)
    profile = active_embedding_profile(flagged)
    embedder = FakeEmbeddingAdapter(model=profile.model, dimensions=profile.dimensions)
    indexer = ChunkIndexer(store=store, embedder=embedder, profile=profile)
    ws = uuid.uuid4()
    video = uuid.uuid4()
    chunk = _chunk("Dense only retrieval path for semantic matches.", uuid.uuid4())
    await indexer.index_chunks(
        chunks=[chunk],
        workspace_id=ws,
        video_id=video,
        source_asset_id=uuid.uuid4(),
        source_revision=1,
    )
    query = HybridQueryService(store=store, embedder=embedder, profile=profile, settings=flagged)
    result = await query.search_authorized(
        authorized=AuthorizedScope(
            workspace_id=ws,
            scope_kind="video",
            scope_id=video,
            video_ids=(video,),
        ),
        query_text="semantic matches",
    )
    assert result.mode == "dense_only"
    assert result.dense_only_flag is True


@pytest.mark.asyncio
async def test_cross_tenant_scope_resolution(settings: Settings) -> None:
    engine = create_engine(settings, url="sqlite+aiosqlite://")
    session_factory = create_session_factory(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()
    video_a = uuid.uuid4()
    video_b = uuid.uuid4()

    async with session_factory() as db:
        assert isinstance(db, AsyncSession)
        # Minimal identity FKs: create workspaces via raw Video inserts need workspace rows.
        from app.db.models import User, Workspace

        user = User(
            id=uuid.uuid4(),
            email="phase07@example.com",
            password_hash="x",
            status="active",
        )
        db.add(user)
        await db.flush()
        for ws_id, name in ((ws_a, "A"), (ws_b, "B")):
            db.add(
                Workspace(
                    id=ws_id,
                    name=name,
                    owner_user_id=user.id,
                )
            )
        await db.flush()
        db.add(
            Video(
                id=video_a,
                workspace_id=ws_a,
                youtube_video_id="vidA",
                title="A",
                status="ready",
            )
        )
        db.add(
            Video(
                id=video_b,
                workspace_id=ws_b,
                youtube_video_id="vidB",
                title="B",
                status="ready",
            )
        )
        await db.commit()

    async with session_factory() as db:
        scoped = await resolve_authorized_video_ids(
            db,
            workspace_id=ws_a,
            scope_kind="video",
            scope_id=video_a,
        )
        assert scoped.video_ids == (video_a,)

        with pytest.raises(UnauthorizedScopeError):
            await resolve_authorized_video_ids(
                db,
                workspace_id=ws_a,
                scope_kind="video",
                scope_id=video_b,
            )

        with pytest.raises(InvalidRetrievalFilter):
            await resolve_authorized_video_ids(
                db,
                workspace_id=ws_a,
                scope_kind="video",
                scope_id=video_a,
                client_filter={"must": []},
            )

    async with session_factory() as db:
        playlist_id = uuid.uuid4()
        db.add(
            Playlist(
                id=playlist_id,
                workspace_id=ws_a,
                youtube_playlist_id="plA",
                title="Playlist A",
                status="imported",
                total_items=1,
            )
        )
        await db.flush()
        db.add(
            PlaylistItem(
                id=uuid.uuid4(),
                playlist_id=playlist_id,
                video_id=video_a,
                playlist_position=0,
                youtube_video_id="vidA",
                state="available",
            )
        )
        await db.commit()

    async with session_factory() as db:
        pl_scope = await resolve_authorized_video_ids(
            db,
            workspace_id=ws_a,
            scope_kind="playlist",
            scope_id=playlist_id,
        )
        assert pl_scope.video_ids == (video_a,)

    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_rejects_dimension_mismatch(settings: Settings) -> None:
    store = build_vector_store(settings)
    profile = active_embedding_profile(settings)
    collection = store.ensure_collection(
        profile_id=profile.profile_id, dimensions=profile.dimensions
    )
    from app.retrieval.contracts import ChunkIndexRecord

    bad = ChunkIndexRecord(
        chunk_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        video_id=uuid.uuid4(),
        source_asset_id=uuid.uuid4(),
        source_revision=1,
        segment_ids=(uuid.uuid4(),),
        text="fixture",
        dense_vector=[0.1, 0.2, 0.3],  # wrong dim
        embedding_profile=profile.profile_id,
    )
    with pytest.raises(EmbeddingProfileMismatch):
        store.upsert_chunks(
            collection=collection,
            profile_id=profile.profile_id,
            dimensions=profile.dimensions,
            records=[bad],
        )
