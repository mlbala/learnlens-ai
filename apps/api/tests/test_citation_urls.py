"""Server-built citation URLs — never invent timed links for TXT."""

from __future__ import annotations

from app.domain.citation_urls import build_watch_url, sanitize_youtube_video_id


def test_timed_srt_produces_t_link() -> None:
    link = build_watch_url(
        youtube_video_id="dQw4w9WgXcQ",
        start_ms=123_000,
        end_ms=142_000,
        timecode_quality="original",
    )
    assert link.timing_verified is True
    assert link.start_ms == 123_000
    assert link.end_ms == 142_000
    assert link.youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=123s"


def test_plain_txt_never_produces_t_link() -> None:
    link = build_watch_url(
        youtube_video_id="dQw4w9WgXcQ",
        start_ms=None,
        end_ms=None,
        timecode_quality="none",
    )
    assert link.timing_verified is False
    assert link.start_ms is None
    assert link.end_ms is None
    assert link.youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert "t=" not in (link.youtube_url or "")


def test_model_supplied_ms_ignored_without_original_quality() -> None:
    # Even if somehow ms were present, non-original quality must not emit t=.
    link = build_watch_url(
        youtube_video_id="dQw4w9WgXcQ",
        start_ms=181_000,
        end_ms=200_000,
        timecode_quality="none",
    )
    assert link.timing_verified is False
    assert "t=" not in (link.youtube_url or "")


def test_invalid_video_id_rejected() -> None:
    assert sanitize_youtube_video_id("not-valid") is None
    assert sanitize_youtube_video_id("../../etc") is None
    link = build_watch_url(
        youtube_video_id="fixtureSum001",
        start_ms=1000,
        end_ms=2000,
        timecode_quality="original",
    )
    assert link.youtube_url is None
    assert link.timing_verified is False
