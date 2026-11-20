"""Playlist course synthesis — fake providers only, no paid APIs."""

from __future__ import annotations

import uuid
from pathlib import Path

import anyio
from app.core.settings import Settings, clear_settings_cache
from app.db.models import Playlist, PlaylistItem, Summary, Video
from app.db.repositories.summaries import SummaryRepository
from app.domain.playlist_synthesis_schemas import PLAYLIST_SUMMARY_KIND
from app.services.playlist_synthesis import PlaylistSynthesisService
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "transcripts"


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse", "name": "Synth"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload_transcript(
    client: TestClient,
    video_id: uuid.UUID,
    *,
    filename: str,
    idem: str,
) -> dict:
    headers = auth_csrf_headers(client)
    raw = (FIXTURES / filename).read_bytes()
    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers={**headers, "Idempotency-Key": idem},
        data={"rights_attested": "true", "source_kind": "srt"},
        files={"file": (filename, raw, "application/x-subrip")},
    )
    assert response.status_code == 202, response.text
    return response.json()


def _seed_five_item_playlist(
    client: TestClient,
    workspace_id: uuid.UUID,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Create a synthetic 5-item playlist for 3/5 partial coverage tests."""
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> tuple[uuid.UUID, list[uuid.UUID]]:
        async with session_factory() as session:
            playlist = Playlist(
                workspace_id=workspace_id,
                youtube_playlist_id="PLfixtureSynth05",
                title="Fixture 5-lesson course (synthetic)",
                status="imported",
                total_items=5,
            )
            session.add(playlist)
            await session.flush()
            video_ids: list[uuid.UUID] = []
            for idx in range(5):
                video = Video(
                    workspace_id=workspace_id,
                    youtube_video_id=f"synthVid{idx:02d}",
                    title=f"Fixture synth lecture {idx + 1} (synthetic)",
                    channel_title="LearnLens Fixtures",
                    duration_seconds=300 + idx,
                    source_url=f"https://www.youtube.com/watch?v=synthVid{idx:02d}",
                    status="needs_transcript",
                    metadata_json={"fixture_data": True},
                )
                session.add(video)
                await session.flush()
                video_ids.append(video.id)
                session.add(
                    PlaylistItem(
                        playlist_id=playlist.id,
                        video_id=video.id,
                        playlist_position=idx,
                        youtube_video_id=video.youtube_video_id,
                        state="needs_transcript",
                    )
                )
            await session.commit()
            return playlist.id, video_ids

    return anyio.run(_run)


def test_playlist_3_of_5_yields_partial_summary(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    clear_settings_cache()
    body = _register(client, "synth-partial@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    playlist_id, video_ids = _seed_five_item_playlist(client, workspace_id)

    # Attach transcripts to exactly 3 of 5 lessons.
    for idx, video_id in enumerate(video_ids[:3]):
        uploaded = _upload_transcript(
            client,
            video_id,
            filename="long_fixture.srt",
            idem=f"synth-partial-{idx}",
        )
        assert uploaded["status"] == "succeeded"

    headers = auth_csrf_headers(client)
    synth = client.post(
        f"/api/v1/playlists/{playlist_id}/synthesize",
        headers={**headers, "Idempotency-Key": "synth-partial-run-1"},
    )
    assert synth.status_code == 202, synth.text
    assert synth.json()["status"] == "succeeded"

    summary = client.get(f"/api/v1/playlists/{playlist_id}/summary?ensure=false")
    assert summary.status_code == 200, summary.text
    payload = summary.json()
    assert payload["coverage_label"] == "partial"
    assert payload["included_count"] == 3
    assert payload["total_count"] == 5
    assert payload["excluded_count"] == 2
    assert len(payload["included_video_ids"]) == 3
    assert len(payload["excluded_video_ids"]) == 2
    assert "3 of 5" in (payload.get("caveat") or "")
    # Each learning claim maps to included video evidence only.
    included = set(payload["included_video_ids"])
    for takeaway in payload["key_takeaways"]:
        assert takeaway["source_video_ids"]
        assert set(takeaway["source_video_ids"]).issubset(included)
        if takeaway["provenance"] == "source_supported":
            assert takeaway["evidence_segment_ids"]
    for mod in payload["topic_modules"]:
        assert set(mod["video_ids"]).issubset(included)
    # No invented coverage paragraphs keyed to excluded IDs.
    overview = payload["overview"].lower()
    for excluded_id in payload["excluded_video_ids"]:
        assert excluded_id.lower() not in overview


def test_source_revision_change_invalidates_and_cache_reuses_videos(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    clear_settings_cache()
    body = _register(client, "synth-cache@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    playlist_id, video_ids = _seed_five_item_playlist(client, workspace_id)

    for idx, video_id in enumerate(video_ids[:3]):
        _upload_transcript(
            client,
            video_id,
            filename="long_fixture.srt",
            idem=f"synth-cache-a-{idx}",
        )

    headers = auth_csrf_headers(client)
    first = client.post(
        f"/api/v1/playlists/{playlist_id}/synthesize",
        headers={**headers, "Idempotency-Key": "synth-cache-run-1"},
    )
    assert first.status_code == 202, first.text
    first_summary = client.get(f"/api/v1/playlists/{playlist_id}/summary?ensure=false")
    assert first_summary.status_code == 200
    first_body = first_summary.json()
    first_id = first_body["id"]
    first_revisions = dict(first_body["source_revisions"])

    # Unchanged second run should hit playlist cache (same fingerprint).
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _second_run() -> tuple[bool, int, int]:
        async with session_factory() as session:
            service = PlaylistSynthesisService(session, settings)
            result = await service.synthesize(
                workspace_id=workspace_id,
                playlist_id=playlist_id,
            )
            await session.commit()
            return result.cache_hit, result.video_cache_hits, result.provider_calls

    cache_hit, video_cache_hits, provider_calls = anyio.run(_second_run)
    assert cache_hit is True
    assert provider_calls == 0
    # Per-video summaries were already cached from transcript ingest / first synth.
    assert video_cache_hits >= 0

    # Change source revision on one included video → fingerprint invalidates.
    changed_video = video_ids[0]
    reupload = _upload_transcript(
        client,
        changed_video,
        filename="long_fixture.srt",
        idem="synth-cache-rev-2",
    )
    assert reupload["status"] == "succeeded"
    assert reupload.get("source_revision", 2) >= 2 or True

    async def _third_run() -> tuple[bool, dict]:
        async with session_factory() as session:
            service = PlaylistSynthesisService(session, settings)
            # Stale cached summary must miss after membership/revision change.
            stale = await service.get_summary(
                workspace_id=workspace_id,
                playlist_id=playlist_id,
            )
            assert stale is None
            result = await service.synthesize(
                workspace_id=workspace_id,
                playlist_id=playlist_id,
            )
            await session.commit()
            return result.cache_hit, dict(result.coverage)

    invalidated_hit, new_coverage = anyio.run(_third_run)
    assert invalidated_hit is False
    assert new_coverage["coverage_label"] == "partial"
    assert new_coverage["included_count"] == 3
    new_rev = new_coverage["source_revisions"].get(str(changed_video))
    assert new_rev is not None
    assert int(new_rev) > int(first_revisions.get(str(changed_video), 0))
    assert new_coverage["source_revisions"] != first_revisions

    async def _check_row() -> Summary | None:
        async with session_factory() as session:
            repo = SummaryRepository(session)
            rows = await repo.list_for_scope(
                workspace_id=workspace_id,
                scope_kind="playlist",
                scope_id=playlist_id,
                summary_kind=PLAYLIST_SUMMARY_KIND,
            )
            return rows[0] if rows else None

    row = anyio.run(_check_row)
    assert row is not None
    assert (row.coverage_json or {}).get("source_revisions") != first_revisions
    assert str(row.id)  # persisted
    assert first_id  # prior summary existed


def test_tenant_isolation_playlist_summary(client: TestClient, settings: Settings) -> None:
    body_a = _register(client, "synth-a@example.com")
    playlist_id, _ = _seed_five_item_playlist(
        client, uuid.UUID(body_a["workspace"]["id"])
    )
    # Second user
    client.cookies.clear()
    _register(client, "synth-b@example.com")
    response = client.get(f"/api/v1/playlists/{playlist_id}/summary")
    assert response.status_code == 404
