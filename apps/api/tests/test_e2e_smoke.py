"""Local end-to-end smoke — fixture video, partial playlist, adversarial transcript.

Uses fake AI / YouTube providers only. All content is synthetic fixture data,
not real YouTube captions. No paid network calls.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import anyio
from app.core.settings import Settings, clear_settings_cache
from app.db.models import PlaylistItem, Video
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import TEST_PASSWORD, auth_csrf_headers

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "fixtures" / "transcripts"
MALICIOUS_VTT = FIXTURES / "malicious_prompt.vtt"
SAMPLE_SRT = FIXTURES / "sample.srt"


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "name": "Smoke"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(
    client: TestClient,
    video_id: str,
    *,
    path: Path,
    source_kind: str,
    content_type: str,
    idem: str,
) -> dict:
    headers = auth_csrf_headers(client)
    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers={**headers, "Idempotency-Key": idem},
        data={"rights_attested": "true", "source_kind": source_kind},
        files={"file": (path.name, path.read_bytes(), content_type)},
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_e2e_fixture_video_partial_playlist_adversarial_transcript(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    """G6-style local smoke: video → transcript → partial playlist → adversarial VTT."""
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    clear_settings_cache()

    _register(client, "e2e-smoke@example.com")
    headers = auth_csrf_headers(client)

    # --- Example fixture video + authorized SRT ---
    imported = client.post(
        "/api/v1/videos/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/watch?v=vidPublic01"},
    )
    assert imported.status_code == 200, imported.text
    video = imported.json()["video"]
    assert video["status"] == "needs_transcript"
    assert video["transcript_access"] is False
    assert "fixture" in (video.get("title") or "").lower() or video.get("metadata_json", {}).get(
        "fixture_data"
    )

    srt_job = _upload(
        client,
        video["id"],
        path=SAMPLE_SRT,
        source_kind="srt",
        content_type="application/x-subrip",
        idem="e2e-srt-1",
    )
    assert srt_job["status"] == "succeeded"
    assert srt_job["timecode_quality"] == "original"
    ready = client.get(f"/api/v1/videos/{video['id']}")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["transcript_access"] is True

    # --- Partial playlist (fixture course includes unavailable + needs_transcript) ---
    playlist_resp = client.post(
        "/api/v1/playlists/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/playlist?list=PLfixtureCourse01"},
    )
    assert playlist_resp.status_code == 200, playlist_resp.text
    playlist = playlist_resp.json()["playlist"]
    coverage = playlist["coverage"]
    assert coverage["total"] == 7
    assert coverage["unavailable"] == 3
    assert coverage["needs_transcript"] >= 1
    assert playlist_resp.json()["transcript_from_url"] is False

    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory
    playlist_id = uuid.UUID(playlist["id"])

    async def _public_needs_transcript() -> list[uuid.UUID]:
        async with session_factory() as session:
            result = await session.execute(
                select(PlaylistItem, Video)
                .join(Video, PlaylistItem.video_id == Video.id)
                .where(PlaylistItem.playlist_id == playlist_id)
                .order_by(PlaylistItem.playlist_position)
            )
            ids: list[uuid.UUID] = []
            for item, vid in result.all():
                if item.state == "needs_transcript" and vid.youtube_video_id.startswith(
                    "vidPublic"
                ):
                    ids.append(vid.id)
            return ids

    public_ids = anyio.run(_public_needs_transcript)
    assert len(public_ids) >= 2
    for idx, vid_id in enumerate(public_ids[:2]):
        job = _upload(
            client,
            str(vid_id),
            path=SAMPLE_SRT,
            source_kind="srt",
            content_type="application/x-subrip",
            idem=f"e2e-playlist-srt-{idx}",
        )
        assert job["status"] == "succeeded"

    detail = client.get(f"/api/v1/playlists/{playlist['id']}")
    assert detail.status_code == 200
    cov = detail.json()["coverage"]
    assert cov["ready"] >= 2
    assert cov["total"] == 7
    assert cov["ready"] < cov["total"]
    assert cov["unavailable"] == 3

    # --- Adversarial transcript treated as data (no secret leak in job payload) ---
    adv_import = client.post(
        "/api/v1/videos/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/watch?v=vidPublic05"},
    )
    assert adv_import.status_code == 200, adv_import.text
    adv_video_id = adv_import.json()["video"]["id"]
    assert MALICIOUS_VTT.is_file(), "malicious_prompt.vtt fixture missing"
    adv_job = _upload(
        client,
        adv_video_id,
        path=MALICIOUS_VTT,
        source_kind="vtt",
        content_type="text/vtt",
        idem="e2e-adv-vtt",
    )
    assert adv_job["status"] == "succeeded"
    blob = str(adv_job).lower()
    assert "sk-live" not in blob
    assert "api_key=" not in blob
    assert "attacker.example" not in blob

    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
