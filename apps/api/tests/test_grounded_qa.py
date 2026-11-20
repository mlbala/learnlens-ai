"""Phase 08 — grounded chat Q&A with verified citations (fake providers only)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import anyio
from app.ai.contracts import ModelRequest, ModelResult, ModelUsage
from app.ai.embeddings.fake import FakeEmbeddingAdapter
from app.core.settings import Settings, clear_settings_cache
from app.db.repositories import SourceAssetRepository, TranscriptSegmentRepository
from app.db.seed import seed_fixture_video
from app.domain.chunking import SegmentRef, chunk_segments
from app.retrieval.factory import build_vector_store, reset_memory_store
from app.retrieval.indexer import ChunkIndexer
from app.retrieval.profile import active_embedding_profile
from app.services.grounded_qa import GroundedQaService
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "transcripts"


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse", "name": "QA Tester"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_video(
    client: TestClient,
    settings: Settings,
    workspace_id: uuid.UUID,
    *,
    youtube_video_id: str = "dQw4w9WgXcQ",
    title: str = "Fixture lecture (synthetic)",
) -> uuid.UUID:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> uuid.UUID:
        async with session_factory() as session:
            video_id = await seed_fixture_video(
                session,
                settings,
                workspace_id=workspace_id,
                youtube_video_id=youtube_video_id,
                title=title,
            )
            await session.commit()
            return video_id

    return anyio.run(_run)


def _upload(
    client: TestClient,
    video_id: uuid.UUID,
    *,
    filename: str,
    source_kind: str,
    idem: str,
) -> dict:
    headers = auth_csrf_headers(client)
    raw = (FIXTURES / filename).read_bytes()
    mime = {
        "srt": "application/x-subrip",
        "vtt": "text/vtt",
        "txt": "text/plain",
    }[source_kind]
    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers={**headers, "Idempotency-Key": idem},
        data={"rights_attested": "true", "source_kind": source_kind},
        files={"file": (filename, raw, mime)},
    )
    assert response.status_code == 202, response.text
    return response.json()


def _index_video(
    client: TestClient,
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    video_id: uuid.UUID,
) -> int:
    """Index current Postgres segments into the shared memory vector store."""
    reset_memory_store()
    clear_settings_cache()
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory
    profile = active_embedding_profile(settings)
    store = build_vector_store(settings)
    embedder = FakeEmbeddingAdapter(model=profile.model, dimensions=profile.dimensions)
    indexer = ChunkIndexer(store=store, embedder=embedder, profile=profile)

    async def _run() -> int:
        async with session_factory() as session:
            assets = SourceAssetRepository(session)
            segments = TranscriptSegmentRepository(session)
            asset = await assets.latest_for_video(
                video_id=video_id,
                workspace_id=workspace_id,
            )
            assert asset is not None
            rows = await segments.list_for_asset(
                asset_id=asset.id,
                workspace_id=workspace_id,
            )
            refs = [
                SegmentRef(
                    id=r.id,
                    ordinal=r.ordinal,
                    text=r.text,
                    start_ms=r.start_ms,
                    end_ms=r.end_ms,
                    content_hash=r.content_hash,
                )
                for r in rows
            ]
            chunks = chunk_segments(refs)
            result = await indexer.index_chunks(
                chunks=chunks,
                workspace_id=workspace_id,
                video_id=video_id,
                source_asset_id=asset.id,
                source_revision=asset.source_revision,
                title="Fixture lecture",
            )
            await session.commit()
            return int(result["upserted"])

    return anyio.run(_run)


class InventingTextAdapter:
    """Returns a citation UUID that is not in the evidence packet."""

    provider = "fake"
    model = "fake-invent-v1"

    def __init__(self, invented_id: str) -> None:
        self._invented = invented_id
        from app.ai.contracts import ModelCapabilities

        self.capabilities = ModelCapabilities(
            supports_json_schema=True,
            supports_stream=False,
            supports_vision=False,
            supports_batch=False,
            max_context_tokens=32_000,
        )

    async def generate_structured(self, request: ModelRequest) -> ModelResult:
        return ModelResult(
            parsed={
                "answer": "Invented citation answer.",
                "claims": [
                    {
                        "text": "This cites a fabricated segment.",
                        "citation_segment_ids": [self._invented],
                    }
                ],
                "unsupported": False,
                "confidence_label": "supported",
            },
            usage=ModelUsage(
                input_tokens=1,
                output_tokens=1,
                provider=self.provider,
                model=self.model,
                request_id="fake-invent",
                tokens_estimated=True,
            ),
        )

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}


def test_timed_evidence_cites_correct_video_segment_time(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    monkeypatch.setenv("QDRANT_VECTOR_STORE", "memory")
    clear_settings_cache()
    reset_memory_store()
    body = _register(client, "qa-timed@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    uploaded = _upload(
        client, video_id, filename="sample.srt", source_kind="srt", idem="qa-srt-1"
    )
    assert uploaded["timecode_quality"] == "original"
    assert _index_video(client, settings, workspace_id=workspace_id, video_id=video_id) >= 1

    headers = auth_csrf_headers(client)
    thread = client.post(
        "/api/v1/chat/threads",
        headers=headers,
        json={"scope_kind": "video", "scope_id": str(video_id), "title": "Listening"},
    )
    assert thread.status_code == 200, thread.text
    thread_id = thread.json()["id"]

    answer = client.post(
        f"/api/v1/chat/threads/{thread_id}/messages",
        headers=headers,
        json={
            "question": "What about clarifying questions and listening?",
            "explanation_mode": "standard",
        },
    )
    assert answer.status_code == 200, answer.text
    payload = answer.json()
    assert payload["unsupported"] is False
    assistant = payload["assistant_message"]
    assert assistant["citations"], "expected at least one verified citation"
    cite = assistant["citations"][0]
    assert cite["video_id"] == str(video_id)
    assert cite["timing_verified"] is True
    assert cite["start_ms"] is not None
    assert cite["youtube_url"] is not None
    assert "&t=" in cite["youtube_url"]
    assert cite["youtube_url"].startswith("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    uuid.UUID(cite["segment_id"])
    for claim in assistant["claims"]:
        assert claim["citation_segment_ids"]
        for sid in claim["citation_segment_ids"]:
            uuid.UUID(sid)


def test_plain_txt_never_produces_timestamp_link(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    monkeypatch.setenv("QDRANT_VECTOR_STORE", "memory")
    clear_settings_cache()
    reset_memory_store()
    body = _register(client, "qa-txt@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(
        client, settings, workspace_id, youtube_video_id="abcdefghijk"
    )
    uploaded = _upload(
        client, video_id, filename="sample.txt", source_kind="txt", idem="qa-txt-1"
    )
    assert uploaded["timecode_quality"] == "none"
    assert _index_video(client, settings, workspace_id=workspace_id, video_id=video_id) >= 1

    headers = auth_csrf_headers(client)
    thread = client.post(
        "/api/v1/chat/threads",
        headers=headers,
        json={"scope_kind": "video", "scope_id": str(video_id)},
    )
    assert thread.status_code == 200, thread.text
    thread_id = thread.json()["id"]
    answer = client.post(
        f"/api/v1/chat/threads/{thread_id}/messages",
        headers=headers,
        json={"question": "What does the fixture transcript say?", "explanation_mode": "simple"},
    )
    assert answer.status_code == 200, answer.text
    payload = answer.json()
    assert payload["unsupported"] is False
    for cite in payload["assistant_message"]["citations"]:
        assert cite["timing_verified"] is False
        assert cite["start_ms"] is None
        assert cite["end_ms"] is None
        assert cite["youtube_url"] is not None
        assert "t=" not in cite["youtube_url"]
    for analogy in payload["assistant_message"]["analogies"]:
        assert analogy["origin"] == "ai_generated_illustration"


def test_invented_model_citation_rejected(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    monkeypatch.setenv("QDRANT_VECTOR_STORE", "memory")
    clear_settings_cache()
    reset_memory_store()
    body = _register(client, "qa-invent@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    _upload(client, video_id, filename="sample.srt", source_kind="srt", idem="qa-inv-1")
    assert _index_video(client, settings, workspace_id=workspace_id, video_id=video_id) >= 1

    invented = str(uuid.uuid4())
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> dict[str, Any]:
        async with session_factory() as session:
            service = GroundedQaService(
                session,
                settings,
                text_model=InventingTextAdapter(invented),
            )
            thread = await service.create_thread(
                workspace_id=workspace_id,
                created_by=uuid.UUID(body["user"]["id"]),
                scope_kind="video",
                scope_id=video_id,
            )
            result = await service.ask(
                thread_id=thread.id,
                workspace_id=workspace_id,
                question="What should I do first?",
            )
            await session.commit()
            return {
                "unsupported": result.unsupported,
                "citations": result.citations,
                "dropped": result.dropped_citation_ids,
                "answer": result.answer,
            }

    out = anyio.run(_run)
    assert out["unsupported"] is True
    assert out["citations"] == []
    assert invented in out["dropped"]
    assert "evidence" in out["answer"].lower()


def test_wrong_tenant_thread_inaccessible(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    clear_settings_cache()
    a = _register(client, "qa-tenant-a@example.com")
    workspace_a = uuid.UUID(a["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_a)
    headers_a = auth_csrf_headers(client)
    thread = client.post(
        "/api/v1/chat/threads",
        headers=headers_a,
        json={"scope_kind": "video", "scope_id": str(video_id)},
    )
    assert thread.status_code == 200, thread.text
    thread_id = thread.json()["id"]

    # Switch to another tenant by registering a second user (new cookies).
    client.cookies.clear()
    _register(client, "qa-tenant-b@example.com")
    headers_b = auth_csrf_headers(client)
    denied = client.post(
        f"/api/v1/chat/threads/{thread_id}/messages",
        headers=headers_b,
        json={"question": "Can I read their thread?"},
    )
    assert denied.status_code == 404, denied.text
    listed = client.get(f"/api/v1/chat/threads/{thread_id}/messages")
    assert listed.status_code == 404, listed.text


def test_insufficient_evidence_refuses(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    monkeypatch.setenv("QDRANT_VECTOR_STORE", "memory")
    clear_settings_cache()
    reset_memory_store()
    body = _register(client, "qa-refuse@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    # No transcript / no index → empty evidence packet → abstention.
    headers = auth_csrf_headers(client)
    thread = client.post(
        "/api/v1/chat/threads",
        headers=headers,
        json={"scope_kind": "video", "scope_id": str(video_id)},
    )
    assert thread.status_code == 200, thread.text
    thread_id = thread.json()["id"]
    answer = client.post(
        f"/api/v1/chat/threads/{thread_id}/messages",
        headers=headers,
        json={"question": "What is covered in this video?"},
    )
    assert answer.status_code == 200, answer.text
    payload = answer.json()
    assert payload["unsupported"] is True
    assert payload["confidence_label"] == "abstain"
    assert payload["assistant_message"]["citations"] == []
    assert "evidence" in payload["assistant_message"]["content"].lower()
