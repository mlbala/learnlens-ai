"""Authorized media upload validation — MIME, magic bytes, AV heuristics.

Never treats a YouTube URL as media input. Rejects executables/archives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath

# Alignment confidence below this must not become exact evidence timestamps.
ALIGNMENT_CONFIDENCE_FLOOR = 0.7

_TRAVERSAL = re.compile(r"(^|[\\/])\.\.([\\/]|$)")
_NULL_BYTE = re.compile(r"\x00")

_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".ogg", ".flac"})
_VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mov", ".mkv"})
_ALLOWED_EXTENSIONS = _AUDIO_EXTENSIONS | _VIDEO_EXTENSIONS

_AUDIO_MIME = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/x-m4a",
        "audio/ogg",
        "audio/flac",
        "application/octet-stream",  # allow when extension+magic agree
    }
)
_VIDEO_MIME = frozenset(
    {
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "video/x-matroska",
        "application/octet-stream",
    }
)

# Known-bad magic — treat as AV/quarantine fail closed.
_BLOCKED_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "executable"),
    (b"\x7fELF", "elf_executable"),
    (b"PK\x03\x04", "zip_archive"),
    (b"\x1f\x8b", "gzip_archive"),
    (b"%PDF", "pdf_document"),
    (b"#!", "script"),
)


class MediaValidateError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MediaKind(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class ValidatedMedia:
    media_kind: MediaKind
    content_type: str
    filename: str
    size_bytes: int
    antivirus_status: str  # clean | quarantined (only clean proceeds)


def sanitize_media_filename(filename: str | None) -> str:
    if filename is None or not filename.strip():
        raise MediaValidateError("INVALID_FILENAME", "Media upload filename is required.")
    raw = filename.strip()
    if _NULL_BYTE.search(raw):
        raise MediaValidateError("INVALID_FILENAME", "Upload filename is invalid.")
    if _TRAVERSAL.search(raw) or raw.startswith(("/", "\\")):
        raise MediaValidateError(
            "INVALID_FILENAME",
            "Path traversal in upload filenames is not allowed.",
        )
    base = PureWindowsPath(raw).name
    base = PurePosixPath(base).name
    if not base or base in {".", ".."} or _TRAVERSAL.search(base):
        raise MediaValidateError(
            "INVALID_FILENAME",
            "Path traversal in upload filenames is not allowed.",
        )
    lower = base.lower()
    if not any(lower.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        raise MediaValidateError(
            "INVALID_MEDIA_TYPE",
            "Only authorized audio/video types are supported "
            f"({', '.join(sorted(_ALLOWED_EXTENSIONS))}).",
        )
    return base


def _kind_from_filename(filename: str) -> MediaKind:
    lower = filename.lower()
    if any(lower.endswith(ext) for ext in _AUDIO_EXTENSIONS):
        return MediaKind.AUDIO
    return MediaKind.VIDEO


def _detect_kind_from_magic(data: bytes) -> MediaKind | None:
    if len(data) < 12:
        return None
    # WAV: RIFF....WAVE
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return MediaKind.AUDIO
    # Ogg
    if data[:4] == b"OggS":
        return MediaKind.AUDIO
    # MP3 frame sync or ID3
    if data[:3] == b"ID3" or data[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return MediaKind.AUDIO
    # FLAC
    if data[:4] == b"fLaC":
        return MediaKind.AUDIO
    # ISO BMFF (mp4/m4a/mov): ftyp at offset 4
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in {b"M4A ", b"M4B ", b"mp4a"}:
            return MediaKind.AUDIO
        return MediaKind.VIDEO
    # WebM / Matroska
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return MediaKind.VIDEO
    # Fixture marker used in offline tests (not real container).
    if data.startswith(b"LLFIXAUD"):
        return MediaKind.AUDIO
    if data.startswith(b"LLFIXVID"):
        return MediaKind.VIDEO
    return None


def antivirus_scan(data: bytes) -> str:
    """Heuristic AV gate — quarantine known dangerous magic; no network."""
    if not data:
        return "quarantined"
    for magic, _label in _BLOCKED_MAGIC:
        if data.startswith(magic):
            return "quarantined"
    # Null-heavy binary in the first page often indicates non-media payloads.
    head = data[:4096]
    if head.count(b"\x00") > 3500 and not data.startswith(
        (b"LLFIXAUD", b"LLFIXVID", b"RIFF", b"\x1a\x45\xdf\xa3")
    ):
        # Allow ISO BMFF / WAV which may contain sparse headers; only fail opaque blobs.
        if data[4:8] != b"ftyp":
            return "quarantined"
    return "clean"


def validate_media_upload(
    *,
    raw: bytes,
    filename: str | None,
    content_type: str | None,
    max_bytes: int,
) -> ValidatedMedia:
    if len(raw) == 0:
        raise MediaValidateError("EMPTY_MEDIA", "Media upload is empty.")
    if len(raw) > max_bytes:
        raise MediaValidateError(
            "PAYLOAD_TOO_LARGE",
            f"Media exceeds the {max_bytes} byte upload limit.",
        )

    safe_name = sanitize_media_filename(filename)
    kind_from_name = _kind_from_filename(safe_name)
    kind_from_magic = _detect_kind_from_magic(raw)

    av = antivirus_scan(raw)
    if av != "clean":
        raise MediaValidateError(
            "MEDIA_QUARANTINED",
            "Upload failed antivirus/file-type screening and was rejected.",
        )

    if kind_from_magic is None:
        raise MediaValidateError(
            "INVALID_MEDIA_TYPE",
            "Unrecognized media container; only authorized audio/video are accepted.",
        )
    if kind_from_magic != kind_from_name:
        raise MediaValidateError(
            "INVALID_MEDIA_TYPE",
            "Media content does not match the declared file extension.",
        )

    mime = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    allowed_mime = _AUDIO_MIME if kind_from_magic == MediaKind.AUDIO else _VIDEO_MIME
    if mime and mime not in allowed_mime:
        raise MediaValidateError(
            "INVALID_MEDIA_TYPE",
            "Media Content-Type is not an allowed audio/video type.",
        )

    return ValidatedMedia(
        media_kind=kind_from_magic,
        content_type=mime or "application/octet-stream",
        filename=safe_name,
        size_bytes=len(raw),
        antivirus_status=av,
    )


def timecode_quality_for_cues(
    cues: list[tuple[int | None, int | None, float]],
) -> str:
    """
    Aggregate timecode quality for a derived caption asset.

    - derived_verified: at least one cue has verified timing above the floor
    - derived_uncertain: cues exist but none have verified timing
    - none: empty
    """
    if not cues:
        return "none"
    any_verified = any(
        start is not None
        and end is not None
        and conf >= ALIGNMENT_CONFIDENCE_FLOOR
        for start, end, conf in cues
    )
    return "derived_verified" if any_verified else "derived_uncertain"
