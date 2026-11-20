"""Phase 17 — opt-in authorized media ingest (fake STT/vision; no YouTube downloads)."""

from __future__ import annotations

import uuid
from pathlib import Path

import anyio
from app.core.settings import Settings, clear_settings_cache
from app.db.models import MediaAsset, MediaFrame, SourceAsset, TranscriptSegment, Video
from app.db.seed import seed_fixture_video
from app.domain.citation_urls import timing_is_verified
from app.domain.media_validate import validate_media_upload
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "media"


def _register(client: TestClient, email: str = "media@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Media User"},
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
                youtube_video_id="fixtureMedia01",
                title="Fixture video for media tests (synthetic)",
            )
            await session.commit()
            return video_id

    return anyio.run(_run)


def _enable_media(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MEDIA_PROCESSING_ENABLED", "true")
    monkeypatch.setenv("MEDIA_STORAGE_PATH", str(tmp_path / "media-store"))
    monkeypatch.setenv("AI_MEDIA_PROVIDER", "fake")
    monkeypatch.setenv("USAGE_DAILY_MEDIA_JOBS", "100")
    clear_settings_cache()


def test_media_disabled_by_default(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("MEDIA_PROCESSING_ENABLED", "false")
    monkeypatch.setenv("MEDIA_STORAGE_PATH", str(tmp_path / "media-store"))
    clear_settings_cache()
    body = _register(client)
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    audio = (FIXTURES / "sample_audio.wav").read_bytes()

    response = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-off-1"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_audio.wav", audio, "audio/wav")},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "MEDIA_PROCESSING_DISABLED"


def test_rights_and_provider_consent_required(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    _enable_media(monkeypatch, tmp_path)
    body = _register(client, email="media-consent@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    audio = (FIXTURES / "sample_audio.wav").read_bytes()

    no_rights = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-norights"},
        data={
            "rights_attested": "false",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_audio.wav", audio, "audio/wav")},
    )
    assert no_rights.status_code == 403
    assert no_rights.json()["error"]["code"] == "RIGHTS_ATTESTATION_REQUIRED"

    no_consent = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-noconsent"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "false",
        },
        files={"file": ("sample_audio.wav", audio, "audio/wav")},
    )
    assert no_consent.status_code == 403
    assert no_consent.json()["error"]["code"] == "PROVIDER_TRANSFER_CONSENT_REQUIRED"


def test_authorized_fixture_audio_derives_captions_with_provenance(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    _enable_media(monkeypatch, tmp_path)
    body = _register(client, email="media-ok@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    audio = (FIXTURES / "sample_audio.wav").read_bytes()

    response = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-audio-1"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_audio.wav", audio, "audio/wav")},
    )
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["stage"] == "complete"
    assert payload["media_kind"] == "audio"
    assert payload["timecode_quality"] == "derived_verified"
    assert payload["source_asset_id"] is not None

    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _check() -> None:
        async with session_factory() as session:
            asset = (
                await session.execute(
                    select(SourceAsset).where(
                        SourceAsset.id == uuid.UUID(payload["source_asset_id"])
                    )
                )
            ).scalar_one()
            assert asset.source_kind == "licensed_media"
            assert asset.timecode_quality == "derived_verified"
            segs = list(
                (
                    await session.execute(
                        select(TranscriptSegment)
                        .where(TranscriptSegment.asset_id == asset.id)
                        .order_by(TranscriptSegment.ordinal)
                    )
                )
                .scalars()
                .all()
            )
            assert len(segs) == 3
            # High-confidence cues keep timing; uncertain cue is null (no exact evidence).
            assert segs[0].start_ms == 0 and segs[0].end_ms == 2500
            assert segs[2].start_ms is None and segs[2].end_ms is None
            media = (
                await session.execute(
                    select(MediaAsset).where(
                        MediaAsset.id == uuid.UUID(payload["media_asset_id"])
                    )
                )
            ).scalar_one()
            assert media.status == "ready"
            assert media.result_json is not None
            provenance = media.result_json["cue_provenance"]
            assert provenance[0]["timing_verified"] is True
            assert provenance[2]["timing_verified"] is False
            assert provenance[0]["provenance"] == "fixture_data"

    anyio.run(_check)

    assert timing_is_verified(
        start_ms=0, end_ms=2500, timecode_quality="derived_verified"
    )
    assert not timing_is_verified(
        start_ms=0, end_ms=2500, timecode_quality="derived_uncertain"
    )


def test_authorized_fixture_video_extracts_frames(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    _enable_media(monkeypatch, tmp_path)
    body = _register(client, email="media-vid@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    video_bytes = (FIXTURES / "sample_video.mp4").read_bytes()

    response = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-video-1"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_video.mp4", video_bytes, "video/mp4")},
    )
    assert response.status_code == 202, response.text
    media_id = uuid.UUID(response.json()["media_asset_id"])
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _check() -> None:
        async with session_factory() as session:
            frames = list(
                (
                    await session.execute(
                        select(MediaFrame)
                        .where(MediaFrame.media_asset_id == media_id)
                        .order_by(MediaFrame.ordinal)
                    )
                )
                .scalars()
                .all()
            )
            assert len(frames) == 2
            assert frames[0].timestamp_ms == 1000
            assert frames[0].alignment_confidence >= 0.7
            assert frames[1].timestamp_ms is None  # uncertain — no exact evidence
            assert frames[0].provenance == "fixture_data"

    anyio.run(_check)


def test_malware_payload_quarantined(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    _enable_media(monkeypatch, tmp_path)
    body = _register(client, email="media-evil@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    evil = (FIXTURES / "evil.exe").read_bytes()

    response = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-evil-1"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_audio.wav", evil, "audio/wav")},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "MEDIA_QUARANTINED"


def test_media_cpu_cap_enforced(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    _enable_media(monkeypatch, tmp_path)
    monkeypatch.setenv("MEDIA_MAX_CPU_UNITS_PER_JOB", "0.01")
    clear_settings_cache()
    body = _register(client, email="media-cpu@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    video_bytes = (FIXTURES / "sample_video.mp4").read_bytes()

    response = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-cpu-1"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_video.mp4", video_bytes, "video/mp4")},
    )
    # Eager processing fails the job after enqueue; API may still return 202 with failed status
    # or the service raises during eager loop — accept either fail-closed outcome.
    assert response.status_code in {202, 429}, response.text
    if response.status_code == 202:
        assert response.json()["status"] == "failed"
        assert response.json()["stage"] == "error"


def test_media_daily_quota(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    _enable_media(monkeypatch, tmp_path)
    monkeypatch.setenv("USAGE_DAILY_MEDIA_JOBS", "1")
    clear_settings_cache()
    from app.core.policies.usage_policy import configure_usage_policy

    configure_usage_policy(
        daily_chat_messages=1000,
        daily_transcript_jobs=1000,
        daily_media_jobs=1,
    )
    body = _register(client, email="media-quota@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    audio = (FIXTURES / "sample_audio.wav").read_bytes()

    first = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-quota-1"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_audio.wav", audio, "audio/wav")},
    )
    assert first.status_code == 202, first.text

    second = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-quota-2"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_audio.wav", audio + b"x", "audio/wav")},
    )
    assert second.status_code == 429, second.text
    assert second.json()["error"]["code"] == "MEDIA_QUOTA_EXCEEDED"


def test_deletion_removes_frames_media_and_storage(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    _enable_media(monkeypatch, tmp_path)
    body = _register(client, email="media-del@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    headers = auth_csrf_headers(client)
    video_bytes = (FIXTURES / "sample_video.mp4").read_bytes()

    upload = client.post(
        f"/api/v1/videos/{video_id}/media",
        headers={**headers, "Idempotency-Key": "media-del-1"},
        data={
            "rights_attested": "true",
            "provider_transfer_consented": "true",
        },
        files={"file": ("sample_video.mp4", video_bytes, "video/mp4")},
    )
    assert upload.status_code == 202, upload.text
    media_id = uuid.UUID(upload.json()["media_asset_id"])

    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _storage_key() -> str:
        async with session_factory() as session:
            media = await session.get(MediaAsset, media_id)
            assert media is not None
            return media.storage_key

    storage_key = anyio.run(_storage_key)
    store_root = tmp_path / "media-store"
    assert (store_root / storage_key).is_file()

    deleted = client.delete(
        f"/api/v1/videos/{video_id}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text
    body_del = deleted.json()
    assert body_del["media_removed"] >= 1
    assert body_del["frames_removed"] >= 1
    assert body_del["storage_keys_removed"] >= 1
    assert not (store_root / storage_key).exists()

    async def _gone() -> None:
        async with session_factory() as session:
            assert await session.get(Video, video_id) is None
            media_count = (
                await session.execute(
                    select(func.count()).select_from(MediaAsset).where(
                        MediaAsset.id == media_id
                    )
                )
            ).scalar_one()
            assert media_count == 0
            frame_count = (
                await session.execute(
                    select(func.count()).select_from(MediaFrame).where(
                        MediaFrame.media_asset_id == media_id
                    )
                )
            ).scalar_one()
            assert frame_count == 0

    anyio.run(_gone)


def test_validate_media_upload_unit() -> None:
    audio = (FIXTURES / "sample_audio.wav").read_bytes()
    ok = validate_media_upload(
        raw=audio,
        filename="sample_audio.wav",
        content_type="audio/wav",
        max_bytes=1024 * 1024,
    )
    assert ok.media_kind.value == "audio"
    assert ok.antivirus_status == "clean"
