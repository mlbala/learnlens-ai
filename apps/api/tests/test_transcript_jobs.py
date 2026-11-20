"""Authorized transcript upload + durable jobs — eager Celery, no paid APIs."""

from __future__ import annotations

import uuid
from pathlib import Path

import anyio
from app.core.settings import Settings
from app.db.models import IngestionJob, TranscriptSegment
from app.db.repositories.assets import TranscriptSegmentRepository
from app.db.seed import seed_fixture_video
from app.domain.job_states import JobStage, JobStatus, can_transition
from app.services.transcript_ingest import TranscriptIngestService
from app.storage.local import LocalMockStorage
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "transcripts"


def _register(client: TestClient, email: str = "transcript@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Transcriber"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_video(client: TestClient, settings: Settings, workspace_id: uuid.UUID) -> uuid.UUID:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> uuid.UUID:
        async with session_factory() as session:
            video_id = await seed_fixture_video(
                session,
                settings,
                workspace_id=workspace_id,
                youtube_video_id="fixtureTx001",
                title="Fixture video for transcript tests (synthetic)",
            )
            await session.commit()
            return video_id

    return anyio.run(_run)


def test_srt_upload_creates_segments_with_exact_ms(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    from app.core.settings import clear_settings_cache

    clear_settings_cache()
    body = _register(client)
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    srt = (FIXTURES / "sample.srt").read_bytes()

    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers={**headers, "Idempotency-Key": "srt-upload-1"},
        data={"rights_attested": "true", "source_kind": "srt"},
        files={"file": ("sample.srt", srt, "application/x-subrip")},
    )
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["stage"] == "complete"
    assert payload["percent"] == 100
    assert payload["source_revision"] == 1
    assert payload["timecode_quality"] == "original"

    job = client.get(f"/api/v1/jobs/{payload['job_id']}")
    assert job.status_code == 200
    assert job.json()["status"] == "succeeded"

    video = client.get(f"/api/v1/videos/{video_id}")
    assert video.status_code == 200
    assert video.json()["status"] == "ready"
    assert video.json()["transcript_access"] is True

    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _segments() -> list[TranscriptSegment]:
        async with session_factory() as session:
            repo = TranscriptSegmentRepository(session)
            return await repo.list_for_asset(
                asset_id=uuid.UUID(payload["source_asset_id"]),
                workspace_id=workspace_id,
            )

    segments = anyio.run(_segments)
    assert len(segments) == 2
    assert segments[0].start_ms == 1250
    assert segments[0].end_ms == 4500
    assert "<" not in segments[0].text


def test_txt_upload_null_timestamps(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    from app.core.settings import clear_settings_cache

    clear_settings_cache()
    body = _register(client, "txt-user@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    txt = (FIXTURES / "sample.txt").read_bytes()

    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={"rights_attested": "true", "source_kind": "txt"},
        files={"file": ("sample.txt", txt, "text/plain")},
    )
    assert response.status_code == 202, response.text
    assert response.json()["timecode_quality"] == "none"

    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _check() -> None:
        async with session_factory() as session:
            result = await session.execute(select(TranscriptSegment))
            rows = list(result.scalars().all())
            assert rows
            assert all(r.start_ms is None and r.end_ms is None for r in rows)

    anyio.run(_check)


def test_paste_transcript_without_attestation_forbidden(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    from app.core.settings import clear_settings_cache

    clear_settings_cache()
    body = _register(client, "no-rights@example.com")
    video_id = _seed_video(client, settings, uuid.UUID(body["workspace"]["id"]))
    headers = auth_csrf_headers(client)
    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={
            "rights_attested": "false",
            "source_kind": "paste",
            "paste_text": "Fixture pasted transcript.",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RIGHTS_ATTESTATION_REQUIRED"


def test_malformed_srt_rejected_safely(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    from app.core.settings import clear_settings_cache

    clear_settings_cache()
    body = _register(client, "bad-srt@example.com")
    video_id = _seed_video(client, settings, uuid.UUID(body["workspace"]["id"]))
    headers = auth_csrf_headers(client)
    bad = (FIXTURES / "malformed.srt").read_bytes()
    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={"rights_attested": "true"},
        files={"file": ("bad.srt", bad, "application/x-subrip")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_TIMESTAMP"
    # Must not echo transcript cue body (fixture text).
    assert "should fail" not in response.text.lower()


def test_payload_too_large_returns_413(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    monkeypatch.setenv("TRANSCRIPT_MAX_UPLOAD_BYTES", "64")
    from app.core.settings import clear_settings_cache

    clear_settings_cache()
    # Rebuild app settings on client — use service path via Form after re-creating is heavy;
    # call with oversized body against settings fixture override via monkeypatch on service.
    body = _register(client, "big@example.com")
    video_id = _seed_video(client, settings, uuid.UUID(body["workspace"]["id"]))
    headers = auth_csrf_headers(client)

    # Patch live settings object used by the app.
    client.app.state.settings.transcript_max_upload_bytes = 64
    clear_settings_cache()

    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={"rights_attested": "true", "source_kind": "txt"},
        files={"file": ("big.txt", b"x" * 200, "text/plain")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_cross_tenant_transcript_and_job_denied(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    from app.core.settings import clear_settings_cache

    clear_settings_cache()
    tenant_a = _register(client, "tx-a@example.com")
    workspace_a = uuid.UUID(tenant_a["workspace"]["id"])
    video_a = _seed_video(client, settings, workspace_a)
    headers_a = auth_csrf_headers(client)
    srt = (FIXTURES / "sample.srt").read_bytes()
    uploaded = client.post(
        f"/api/v1/videos/{video_a}/transcripts",
        headers={**headers_a, "Idempotency-Key": "tenant-a-tx"},
        data={"rights_attested": "true"},
        files={"file": ("sample.srt", srt, "application/x-subrip")},
    )
    assert uploaded.status_code == 202
    job_id = uploaded.json()["job_id"]

    client.cookies.clear()
    _register(client, "tx-b@example.com")
    headers_b = auth_csrf_headers(client)

    denied_upload = client.post(
        f"/api/v1/videos/{video_a}/transcripts",
        headers=headers_b,
        data={"rights_attested": "true", "paste_text": "intrusion"},
    )
    assert denied_upload.status_code == 404

    denied_job = client.get(f"/api/v1/jobs/{job_id}")
    assert denied_job.status_code == 404


def test_idempotency_key_replays_same_job(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    from app.core.settings import clear_settings_cache

    clear_settings_cache()
    body = _register(client, "idem@example.com")
    video_id = _seed_video(client, settings, uuid.UUID(body["workspace"]["id"]))
    headers = {**auth_csrf_headers(client), "Idempotency-Key": "same-tx-key"}
    srt = (FIXTURES / "sample.srt").read_bytes()
    first = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={"rights_attested": "true"},
        files={"file": ("sample.srt", srt, "application/x-subrip")},
    )
    second = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={"rights_attested": "true"},
        files={"file": ("sample.srt", srt, "application/x-subrip")},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.json()["replay"] is True


def test_job_state_transitions_are_bounded() -> None:
    assert can_transition(
        from_status=JobStatus.QUEUED,
        from_stage=JobStage.PENDING,
        to_status=JobStatus.RUNNING,
        to_stage=JobStage.VALIDATING,
    )
    assert not can_transition(
        from_status=JobStatus.SUCCEEDED,
        from_stage=JobStage.COMPLETE,
        to_status=JobStatus.QUEUED,
        to_stage=JobStage.PENDING,
    )
    assert not can_transition(
        from_status=JobStatus.QUEUED,
        from_stage=JobStage.PENDING,
        to_status=JobStatus.SUCCEEDED,
        to_stage=JobStage.COMPLETE,
    )


def test_worker_retries_then_succeeds_in_eager_mode(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    """Simulate transient storage miss, then succeed within bounded attempts."""
    store = LocalMockStorage(tmp_path / "retry-store")
    calls = {"n": 0}
    real_get = store.get_bytes

    def flaky_get(key: str) -> bytes:
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyError(key)
        return real_get(key)

    monkeypatch.setattr(store, "get_bytes", flaky_get)

    body = _register(client, "retry@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)

    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> IngestionJob:
        async with session_factory() as session:
            # Use a settings copy with tmp storage path.
            local_settings = Settings(
                _env_file=None,
                environment="test",
                database_url="sqlite+aiosqlite://",
                session_secret="test-session-secret-not-for-prod",
                allow_test_seed=True,
                celery_task_always_eager=True,
                transcript_storage_path=str(tmp_path / "retry-store"),
                transcript_job_max_attempts=3,
                qdrant_url="https://example.cloud.qdrant.io",
                qdrant_api_key="test-key",
            )
            service = TranscriptIngestService(session, local_settings)
            # Patch storage after construction.
            service._storage = store  # noqa: SLF001
            raw = (FIXTURES / "sample.srt").read_bytes()
            result = await service.ingest(
                workspace_id=workspace_id,
                user_id=uuid.UUID(body["user"]["id"]),
                video_id=video_id,
                raw=raw,
                rights_attested=True,
                filename="sample.srt",
                content_type="application/x-subrip",
                source_kind_hint="srt",
                idempotency_key="retry-key-1",
            )
            await session.commit()
            return result.job

    job = anyio.run(_run)
    assert job.status == "succeeded"
    assert job.attempt >= 2
    assert calls["n"] >= 2
