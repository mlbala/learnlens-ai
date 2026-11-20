"""Server-only citation URL builder — never trust model-supplied timestamps/URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Same alphabet as youtube_url.py — keep local to avoid coupling mutations.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass(frozen=True, slots=True)
class BuiltCitationLink:
    youtube_url: str | None
    start_ms: int | None
    end_ms: int | None
    timing_verified: bool


def sanitize_youtube_video_id(raw: str | None) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    candidate = raw.strip()
    if not _VIDEO_ID_RE.fullmatch(candidate):
        return None
    return candidate


def timing_is_verified(
    *,
    start_ms: int | None,
    end_ms: int | None,
    timecode_quality: str | None,
) -> bool:
    """
    Only original caption cues or media-derived *verified* alignment produce jump links.

    ``derived_uncertain`` / ``none`` / TXT never invent exact evidence timestamps.
    """
    if timecode_quality not in {"original", "derived_verified"}:
        return False
    if start_ms is None or end_ms is None:
        return False
    if start_ms < 0 or end_ms < start_ms:
        return False
    return True


def build_watch_url(
    *,
    youtube_video_id: str | None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    timecode_quality: str | None = None,
) -> BuiltCitationLink:
    """
    Build a YouTube watch URL from DB fields only.

    Plain TXT / untimed sources: watch URL without ``t=`` (or None if ID invalid).
    Timed SRT/VTT with original quality: ``&t={seconds}s`` from verified start_ms.
    """
    vid = sanitize_youtube_video_id(youtube_video_id)
    verified = timing_is_verified(
        start_ms=start_ms,
        end_ms=end_ms,
        timecode_quality=timecode_quality,
    )
    if vid is None:
        return BuiltCitationLink(
            youtube_url=None,
            start_ms=None,
            end_ms=None,
            timing_verified=False,
        )
    if verified and start_ms is not None:
        seconds = int(start_ms) // 1000
        return BuiltCitationLink(
            youtube_url=f"https://www.youtube.com/watch?v={vid}&t={seconds}s",
            start_ms=int(start_ms),
            end_ms=int(end_ms) if end_ms is not None else None,
            timing_verified=True,
        )
    return BuiltCitationLink(
        youtube_url=f"https://www.youtube.com/watch?v={vid}",
        start_ms=None,
        end_ms=None,
        timing_verified=False,
    )
