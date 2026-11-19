"""Strict YouTube URL parsing — SSRF-safe; never fetch the user-supplied URL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qs, unquote, urlparse

# Exact allowlisted hostnames (lowercase ASCII). No suffix matching.
_ALLOWED_HOSTS = frozenset(
    {
        "www.youtube.com",
        "youtube.com",
        "m.youtube.com",
        "youtu.be",
    }
)

# YouTube video IDs are 11 chars from the documented alphabet.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
# Playlist IDs: PL/UU/LL/FL/OL prefixes plus alphanumerics; bounded length.
_PLAYLIST_ID_RE = re.compile(r"^(?:PL|UU|LL|FL|OL)[A-Za-z0-9_-]{10,64}$")


class YoutubeUrlKind(StrEnum):
    VIDEO = "video"
    PLAYLIST = "playlist"


@dataclass(frozen=True, slots=True)
class ParsedYoutubeUrl:
    kind: YoutubeUrlKind
    video_id: str | None
    playlist_id: str | None
    canonical_url: str
    # Original input retained for audit only (query redacted to identity params).
    audit_url: str
    # True when watch URL also had list= — UI may offer “Import playlist instead”.
    has_companion_playlist: bool = False
    companion_playlist_id: str | None = None


class YoutubeUrlError(ValueError):
    """Raised when a URL fails allowlist / ID validation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _reject(code: str, message: str) -> None:
    raise YoutubeUrlError(code, message)


def _hostname_is_safe(hostname: str | None) -> bool:
    if hostname is None or hostname == "":
        return False
    # Reject credentials, userinfo-style confusion, trailing dots, IPs, IDNA tricks.
    if "@" in hostname:
        return False
    host = hostname.rstrip(".").lower()
    # Percent-encoded host confusion / unicode / non-ASCII.
    if "%" in host or any(ord(c) > 127 for c in host):
        return False
    # Numeric / IP literals (IPv4 or bracket IPv6).
    if host.startswith("[") or re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        return False
    if "localhost" in host or host.endswith(".local") or host.endswith(".internal"):
        return False
    return host in _ALLOWED_HOSTS


def _validate_video_id(video_id: str | None) -> str:
    if not video_id or not _VIDEO_ID_RE.fullmatch(video_id):
        _reject("INVALID_VIDEO_ID", "YouTube video ID is missing or invalid.")
    return video_id


def _validate_playlist_id(playlist_id: str | None) -> str:
    if not playlist_id or not _PLAYLIST_ID_RE.fullmatch(playlist_id):
        _reject("INVALID_PLAYLIST_ID", "YouTube playlist ID is missing or invalid.")
    return playlist_id


def _audit_url(*, kind: YoutubeUrlKind, video_id: str | None, playlist_id: str | None) -> str:
    """Server-built audit string with only identity query params (no tracking junk)."""
    if kind is YoutubeUrlKind.PLAYLIST and playlist_id:
        return f"https://www.youtube.com/playlist?list={playlist_id}"
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return "https://www.youtube.com/"


def parse_youtube_url(raw: str) -> ParsedYoutubeUrl:
    """
    Parse and canonicalize a user-pasted YouTube URL.

    Never performs network I/O. Rejects non-HTTPS, non-allowlisted hosts,
    credentials, ports other than default, and malformed IDs.
    For ``watch?v=…&list=…``, imports the single video and surfaces the
    companion playlist id for an explicit UI affordance.
    """
    if raw is None or not isinstance(raw, str):
        _reject("INVALID_URL", "URL must be a non-empty string.")
    text = raw.strip()
    if not text or len(text) > 2048:
        _reject("INVALID_URL", "URL is empty or too long.")

    # Block credential embedding before urlparse normalizes oddly.
    if "@" in text.split("://", 1)[-1].split("/", 1)[0]:
        _reject("INVALID_URL", "URLs with embedded credentials are not allowed.")

    parsed = urlparse(text)
    if parsed.scheme.lower() != "https":
        _reject("INVALID_URL", "Only HTTPS YouTube URLs are accepted.")
    if parsed.username or parsed.password:
        _reject("INVALID_URL", "URLs with embedded credentials are not allowed.")
    if parsed.port is not None and parsed.port != 443:
        _reject("INVALID_URL", "Non-default ports are not allowed.")
    if parsed.params:
        _reject("INVALID_URL", "URL parameters segment is not allowed.")

    host = parsed.hostname
    if not _hostname_is_safe(host):
        _reject("INVALID_HOST", "Hostname is not an allowlisted YouTube host.")

    host_l = (host or "").rstrip(".").lower()
    path = unquote(parsed.path or "")
    query = parse_qs(parsed.query, keep_blank_values=False)

    # youtu.be/<video_id>
    if host_l == "youtu.be":
        parts = [p for p in path.split("/") if p]
        if len(parts) != 1:
            _reject("INVALID_URL", "Short YouTube URL path is invalid.")
        video_id = _validate_video_id(parts[0])
        return ParsedYoutubeUrl(
            kind=YoutubeUrlKind.VIDEO,
            video_id=video_id,
            playlist_id=None,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
            audit_url=_audit_url(kind=YoutubeUrlKind.VIDEO, video_id=video_id, playlist_id=None),
        )

    # www.youtube.com / youtube.com / m.youtube.com
    parts = [p for p in path.split("/") if p]

    # /playlist?list=
    if parts == ["playlist"]:
        list_vals = query.get("list") or []
        playlist_id = _validate_playlist_id(list_vals[0] if list_vals else None)
        return ParsedYoutubeUrl(
            kind=YoutubeUrlKind.PLAYLIST,
            video_id=None,
            playlist_id=playlist_id,
            canonical_url=f"https://www.youtube.com/playlist?list={playlist_id}",
            audit_url=_audit_url(
                kind=YoutubeUrlKind.PLAYLIST, video_id=None, playlist_id=playlist_id
            ),
        )

    # /shorts/<id>
    if len(parts) == 2 and parts[0] == "shorts":
        video_id = _validate_video_id(parts[1])
        return ParsedYoutubeUrl(
            kind=YoutubeUrlKind.VIDEO,
            video_id=video_id,
            playlist_id=None,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
            audit_url=_audit_url(kind=YoutubeUrlKind.VIDEO, video_id=video_id, playlist_id=None),
        )

    # /watch?v=
    if parts == ["watch"] or path in {"/watch", "watch"}:
        v_vals = query.get("v") or []
        video_id = _validate_video_id(v_vals[0] if v_vals else None)
        companion: str | None = None
        list_vals = query.get("list") or []
        if list_vals:
            try:
                companion = _validate_playlist_id(list_vals[0])
            except YoutubeUrlError:
                companion = None
        return ParsedYoutubeUrl(
            kind=YoutubeUrlKind.VIDEO,
            video_id=video_id,
            playlist_id=None,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
            audit_url=_audit_url(kind=YoutubeUrlKind.VIDEO, video_id=video_id, playlist_id=None),
            has_companion_playlist=companion is not None,
            companion_playlist_id=companion,
        )

    # /embed/<id> accepted as video (common share form) — still constructed API only.
    if len(parts) == 2 and parts[0] == "embed":
        video_id = _validate_video_id(parts[1])
        return ParsedYoutubeUrl(
            kind=YoutubeUrlKind.VIDEO,
            video_id=video_id,
            playlist_id=None,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
            audit_url=_audit_url(kind=YoutubeUrlKind.VIDEO, video_id=video_id, playlist_id=None),
        )

    _reject("UNSUPPORTED_URL", "URL path is not a supported YouTube video or playlist form.")


def build_watch_url(video_id: str, *, start_seconds: int | None = None) -> str:
    """Server-constructed watch URL; never trust model-generated links."""
    vid = _validate_video_id(video_id)
    if start_seconds is None:
        return f"https://www.youtube.com/watch?v={vid}"
    if start_seconds < 0:
        _reject("INVALID_TIMESTAMP", "start_seconds must be non-negative.")
    return f"https://www.youtube.com/watch?v={vid}&t={int(start_seconds)}s"
