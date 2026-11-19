"""SRT / VTT / TXT transcript parsing with fail-closed timing validation.

Does not invent timestamps. Plain TXT always yields null start/end ms.
Never logs raw cue text.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum


class TranscriptParseError(ValueError):
    """Malformed or policy-violating transcript input (safe public message)."""

    def __init__(self, code: str, message: str, *, cue: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.cue = cue


class SourceKind(StrEnum):
    SRT = "srt"
    VTT = "vtt"
    TXT = "txt"
    PASTE = "paste"


@dataclass(frozen=True, slots=True)
class ParsedCue:
    ordinal: int
    text: str
    start_ms: int | None
    end_ms: int | None


@dataclass(frozen=True, slots=True)
class ParsedTranscript:
    source_kind: SourceKind
    timecode_quality: str  # original | none
    cues: tuple[ParsedCue, ...]
    content_hash: str
    character_count: int


# SRT: 00:00:01,000 or 00:00:01.000 — VTT prefers '.'
_TS_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})[.,](\d{1,3})$")
_ARROW_RE = re.compile(r"\s*-->\s*")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_VTT_NOTE_RE = re.compile(r"^(NOTE|STYLE|REGION)\b", re.IGNORECASE)
_BINARY_HINT = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Reject absurd single cue lengths (> 1 hour).
_MAX_CUE_DURATION_MS = 3_600_000
_MAX_CUES = 50_000


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_utf8(raw: bytes) -> str:
    """Decode UTF-8 (BOM allowed). Reject binary / non-text payloads."""
    if not raw:
        raise TranscriptParseError("EMPTY_TRANSCRIPT", "Transcript content is empty.")
    head = raw[:8]
    if head.startswith((b"PK\x03\x04", b"\x7fELF", b"MZ", b"\x1f\x8b")):
        raise TranscriptParseError(
            "INVALID_TRANSCRIPT_TYPE",
            "Archives and executables are not allowed as transcripts.",
        )
    if _BINARY_HINT.search(raw[:8192]):
        raise TranscriptParseError(
            "INVALID_TRANSCRIPT_ENCODING",
            "Transcript must be UTF-8 text; binary payloads are not allowed.",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TranscriptParseError(
            "INVALID_TRANSCRIPT_ENCODING",
            "Transcript must be valid UTF-8.",
        ) from exc
    if "\x00" in text:
        raise TranscriptParseError(
            "INVALID_TRANSCRIPT_ENCODING",
            "Transcript must be UTF-8 text; binary payloads are not allowed.",
        )
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_presentation_markup(text: str) -> str:
    """Remove HTML/VTT presentation tags for safe UI rendering; keep cue wording."""
    cleaned = _HTML_TAG_RE.sub(" ", text)
    return " ".join(cleaned.split()).strip()


def detect_source_kind(
    *,
    filename: str | None,
    content_type: str | None,
    text: str,
) -> SourceKind:
    """Detect kind from content first, then filename / MIME."""
    lowered = text.lstrip().lower()
    if lowered.startswith("webvtt"):
        return SourceKind.VTT
    if re.match(r"^\d+\s*\n\d{1,2}:\d{2}:\d{2}[.,]\d", text.lstrip()):
        return SourceKind.SRT

    name = (filename or "").lower().strip()
    ctype = (content_type or "").lower().split(";")[0].strip()
    if name.endswith(".vtt") or ctype == "text/vtt":
        return SourceKind.VTT
    if name.endswith(".srt") or ctype == "application/x-subrip":
        return SourceKind.SRT
    if name.endswith(".txt") or ctype in {"text/plain", ""}:
        if "-->" in text and re.search(r"\d{1,2}:\d{2}:\d{2}[.,]\d", text):
            first_lines = [ln.strip() for ln in text.split("\n")[:20] if ln.strip()]
            if first_lines and _looks_like_vtt_body(first_lines):
                return SourceKind.VTT
            return SourceKind.SRT
        return SourceKind.TXT
    raise TranscriptParseError(
        "INVALID_TRANSCRIPT_TYPE",
        "Only .srt, .vtt, and .txt transcripts are supported.",
    )


def _looks_like_vtt_body(lines: list[str]) -> bool:
    for line in lines:
        if "-->" in line:
            return True
        if line.isdigit():
            return False
    return False


def _parse_timestamp_ms(token: str, *, cue: int) -> int:
    match = _TS_RE.match(token.strip())
    if not match:
        raise TranscriptParseError(
            "INVALID_TIMESTAMP",
            f"Malformed timestamp at cue {cue}.",
            cue=cue,
        )
    hours_s, minutes_s, seconds_s, frac_s = match.groups()
    hours = int(hours_s or "0")
    minutes = int(minutes_s)
    seconds = int(seconds_s)
    frac = frac_s.ljust(3, "0")[:3]
    millis = int(frac)
    if minutes >= 60 or seconds >= 60:
        raise TranscriptParseError(
            "INVALID_TIMESTAMP",
            f"Out-of-range timestamp at cue {cue}.",
            cue=cue,
        )
    return ((hours * 3600) + (minutes * 60) + seconds) * 1000 + millis


def _parse_timing_line(line: str, *, cue: int) -> tuple[int, int]:
    parts = _ARROW_RE.split(line.strip(), maxsplit=1)
    if len(parts) != 2:
        raise TranscriptParseError(
            "INVALID_TIMESTAMP",
            f"Missing timing arrow at cue {cue}.",
            cue=cue,
        )
    start_token = parts[0].split()[0] if parts[0].strip() else ""
    end_token = parts[1].split()[0] if parts[1].strip() else ""
    start_ms = _parse_timestamp_ms(start_token, cue=cue)
    end_ms = _parse_timestamp_ms(end_token, cue=cue)
    if start_ms < 0 or end_ms < 0:
        raise TranscriptParseError(
            "INVALID_TIMESTAMP",
            f"Negative timestamp at cue {cue}.",
            cue=cue,
        )
    if end_ms < start_ms:
        raise TranscriptParseError(
            "INVALID_TIMESTAMP",
            f"End before start at cue {cue}.",
            cue=cue,
        )
    if end_ms - start_ms > _MAX_CUE_DURATION_MS:
        raise TranscriptParseError(
            "INVALID_TIMESTAMP",
            f"Absurd cue duration at cue {cue}.",
            cue=cue,
        )
    return start_ms, end_ms


def _enforce_timeline(cues: list[ParsedCue]) -> None:
    prev_end: int | None = None
    for cue in cues:
        if cue.start_ms is None or cue.end_ms is None:
            continue
        if prev_end is not None and cue.start_ms < prev_end:
            raise TranscriptParseError(
                "OVERLAPPING_CUES",
                f"Overlapping or decreasing timeline at cue {cue.ordinal}.",
                cue=cue.ordinal,
            )
        prev_end = cue.end_ms


def parse_srt(text: str) -> list[ParsedCue]:
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: list[ParsedCue] = []
    for block in blocks:
        lines = [ln.rstrip() for ln in block.split("\n")]
        while lines and lines[-1] == "":
            lines.pop()
        if not lines:
            continue
        idx = 0
        if lines[0].strip().isdigit():
            idx = 1
        if idx >= len(lines) or "-->" not in lines[idx]:
            cue_no = len(cues) + 1
            raise TranscriptParseError(
                "INVALID_SRT",
                f"SRT cue {cue_no} is missing a timing line.",
                cue=cue_no,
            )
        cue_no = len(cues) + 1
        start_ms, end_ms = _parse_timing_line(lines[idx], cue=cue_no)
        body = "\n".join(lines[idx + 1 :]).strip()
        if not body:
            raise TranscriptParseError(
                "EMPTY_CUE",
                f"SRT cue {cue_no} has no text.",
                cue=cue_no,
            )
        cues.append(
            ParsedCue(
                ordinal=cue_no,
                text=strip_presentation_markup(body),
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )
        if len(cues) > _MAX_CUES:
            raise TranscriptParseError("TOO_MANY_CUES", "Transcript exceeds cue limit.")
    if not cues:
        raise TranscriptParseError("EMPTY_TRANSCRIPT", "SRT contained no cues.")
    _enforce_timeline(cues)
    return cues


def parse_vtt(text: str) -> list[ParsedCue]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[0].lstrip().upper().startswith("WEBVTT"):
        start_at = 1
        while start_at < len(lines) and lines[start_at].strip() != "":
            start_at += 1
        start_at += 1
    else:
        start_at = 0

    cues: list[ParsedCue] = []
    i = start_at
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if _VTT_NOTE_RE.match(line):
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                i += 1
            continue
        if "-->" not in line:
            i += 1
            if i >= len(lines) or "-->" not in lines[i]:
                cue_no = len(cues) + 1
                raise TranscriptParseError(
                    "INVALID_VTT",
                    f"VTT cue {cue_no} is missing a timing line.",
                    cue=cue_no,
                )
            line = lines[i].strip()
        cue_no = len(cues) + 1
        start_ms, end_ms = _parse_timing_line(line, cue=cue_no)
        i += 1
        body_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "":
            body_lines.append(lines[i])
            i += 1
        body = "\n".join(body_lines).strip()
        if not body:
            raise TranscriptParseError(
                "EMPTY_CUE",
                f"VTT cue {cue_no} has no text.",
                cue=cue_no,
            )
        cues.append(
            ParsedCue(
                ordinal=cue_no,
                text=strip_presentation_markup(body),
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )
        if len(cues) > _MAX_CUES:
            raise TranscriptParseError("TOO_MANY_CUES", "Transcript exceeds cue limit.")
    if not cues:
        raise TranscriptParseError("EMPTY_TRANSCRIPT", "VTT contained no cues.")
    _enforce_timeline(cues)
    return cues


def parse_plain_text(text: str, *, source_kind: SourceKind) -> list[ParsedCue]:
    """Plain TXT / paste — never invents timecodes."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        single = text.strip()
        paragraphs = [single] if single else []
    cues: list[ParsedCue] = []
    for paragraph in paragraphs:
        body = strip_presentation_markup(paragraph)
        if not body:
            continue
        cues.append(
            ParsedCue(ordinal=len(cues) + 1, text=body, start_ms=None, end_ms=None)
        )
    if not cues:
        raise TranscriptParseError("EMPTY_TRANSCRIPT", "Transcript content is empty.")
    if any(c.start_ms is not None or c.end_ms is not None for c in cues):
        raise TranscriptParseError(
            "UNEXPECTED_TIMESTAMPS",
            f"{source_kind.value} transcripts cannot carry timestamps.",
        )
    return cues


def parse_transcript(
    raw: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    source_kind_hint: SourceKind | None = None,
    max_characters: int = 200_000,
) -> ParsedTranscript:
    text = normalize_utf8(raw)
    if len(text) > max_characters:
        raise TranscriptParseError(
            "TRANSCRIPT_TOO_LARGE",
            f"Transcript exceeds the {max_characters} character limit.",
        )

    if source_kind_hint is not None:
        kind = source_kind_hint
    else:
        kind = detect_source_kind(filename=filename, content_type=content_type, text=text)

    if kind in {SourceKind.TXT, SourceKind.PASTE}:
        cues = parse_plain_text(text, source_kind=kind)
        quality = "none"
    elif kind == SourceKind.SRT:
        cues = parse_srt(text)
        quality = "original"
    elif kind == SourceKind.VTT:
        cues = parse_vtt(text)
        quality = "original"
    else:
        raise TranscriptParseError(
            "INVALID_TRANSCRIPT_TYPE",
            "Only .srt, .vtt, and .txt transcripts are supported.",
        )

    digest = sha256_hex(raw)
    return ParsedTranscript(
        source_kind=kind,
        timecode_quality=quality,
        cues=tuple(cues),
        content_hash=digest,
        character_count=len(text),
    )
