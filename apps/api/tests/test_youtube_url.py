"""Malicious URL / SSRF parser tests — no network I/O."""

from __future__ import annotations

import pytest
from app.domain.youtube_url import YoutubeUrlError, YoutubeUrlKind, parse_youtube_url


@pytest.mark.parametrize(
    ("raw", "kind", "video_id", "playlist_id"),
    [
        (
            "https://www.youtube.com/watch?v=vidPublic01",
            YoutubeUrlKind.VIDEO,
            "vidPublic01",
            None,
        ),
        (
            "https://youtu.be/vidPublic02",
            YoutubeUrlKind.VIDEO,
            "vidPublic02",
            None,
        ),
        (
            "https://www.youtube.com/shorts/vidPublic03",
            YoutubeUrlKind.VIDEO,
            "vidPublic03",
            None,
        ),
        (
            "https://m.youtube.com/watch?v=vidPublic04",
            YoutubeUrlKind.VIDEO,
            "vidPublic04",
            None,
        ),
        (
            "https://www.youtube.com/playlist?list=PLfixtureCourse01",
            YoutubeUrlKind.PLAYLIST,
            None,
            "PLfixtureCourse01",
        ),
        (
            "https://www.youtube.com/embed/vidPublic05",
            YoutubeUrlKind.VIDEO,
            "vidPublic05",
            None,
        ),
    ],
)
def test_accepts_allowlisted_forms(
    raw: str,
    kind: YoutubeUrlKind,
    video_id: str | None,
    playlist_id: str | None,
) -> None:
    parsed = parse_youtube_url(raw)
    assert parsed.kind is kind
    assert parsed.video_id == video_id
    assert parsed.playlist_id == playlist_id
    assert parsed.canonical_url.startswith("https://www.youtube.com/")


def test_watch_with_list_imports_single_video_and_surfaces_companion() -> None:
    parsed = parse_youtube_url(
        "https://www.youtube.com/watch?v=vidPublic01&list=PLfixtureCourse01&index=2"
    )
    assert parsed.kind is YoutubeUrlKind.VIDEO
    assert parsed.video_id == "vidPublic01"
    assert parsed.has_companion_playlist is True
    assert parsed.companion_playlist_id == "PLfixtureCourse01"


@pytest.mark.parametrize(
    "raw",
    [
        "http://www.youtube.com/watch?v=vidPublic01",
        "https://youtube.com.evil.example/watch?v=vidPublic01",
        "https://evil.com/youtube.com/watch?v=vidPublic01",
        "https://user:pass@www.youtube.com/watch?v=vidPublic01",
        "https://www.youtube.com:8443/watch?v=vidPublic01",
        "https://127.0.0.1/watch?v=vidPublic01",
        "https://localhost/watch?v=vidPublic01",
        "https://[::1]/watch?v=vidPublic01",
        "https://www.youtube.com.evil.com/watch?v=vidPublic01",
        "https://notyoutube.com/watch?v=vidPublic01",
        "ftp://www.youtube.com/watch?v=vidPublic01",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/watch?v=vidPublic01!!!!!!!!",
        "https://www.youtube.com/playlist?list=bad",
        "https://www.youtube.com/watch",
        "//www.youtube.com/watch?v=vidPublic01",
    ],
)
def test_rejects_malicious_and_malformed(raw: str) -> None:
    with pytest.raises(YoutubeUrlError):
        parse_youtube_url(raw)
