"""Unit tests for SRT/VTT/TXT parsing — exact ms, null TXT timestamps, fail-closed."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.domain.transcript_parse import (
    SourceKind,
    TranscriptParseError,
    parse_transcript,
    strip_presentation_markup,
)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "transcripts"


def test_srt_retains_exact_milliseconds() -> None:
    raw = (FIXTURES / "sample.srt").read_bytes()
    parsed = parse_transcript(raw, filename="sample.srt")
    assert parsed.source_kind == SourceKind.SRT
    assert parsed.timecode_quality == "original"
    assert parsed.cues[0].start_ms == 1250
    assert parsed.cues[0].end_ms == 4500
    assert parsed.cues[1].start_ms == 4500
    assert parsed.cues[1].end_ms == 8000


def test_vtt_retains_exact_milliseconds() -> None:
    raw = (FIXTURES / "sample.vtt").read_bytes()
    parsed = parse_transcript(raw, filename="sample.vtt")
    assert parsed.source_kind == SourceKind.VTT
    assert parsed.cues[0].start_ms == 1250
    assert parsed.cues[0].end_ms == 4500


def test_txt_never_has_timecodes() -> None:
    raw = (FIXTURES / "sample.txt").read_bytes()
    parsed = parse_transcript(raw, filename="sample.txt")
    assert parsed.source_kind == SourceKind.TXT
    assert parsed.timecode_quality == "none"
    assert parsed.cues
    assert all(c.start_ms is None and c.end_ms is None for c in parsed.cues)


def test_paste_hint_forces_null_timestamps() -> None:
    raw = b"Plain pasted fixture text without timing."
    parsed = parse_transcript(raw, source_kind_hint=SourceKind.PASTE)
    assert parsed.source_kind == SourceKind.PASTE
    assert parsed.cues[0].start_ms is None
    assert parsed.cues[0].end_ms is None


def test_malformed_srt_end_before_start_fails() -> None:
    raw = (FIXTURES / "malformed.srt").read_bytes()
    with pytest.raises(TranscriptParseError) as exc:
        parse_transcript(raw, filename="malformed.srt")
    assert exc.value.code == "INVALID_TIMESTAMP"
    assert exc.value.cue == 1


def test_overlapping_cues_fail() -> None:
    raw = (
        b"1\n00:00:01,000 --> 00:00:05,000\nFirst\n\n"
        b"2\n00:00:04,000 --> 00:00:06,000\nOverlap\n"
    )
    with pytest.raises(TranscriptParseError) as exc:
        parse_transcript(raw, filename="overlap.srt")
    assert exc.value.code == "OVERLAPPING_CUES"


def test_binary_payload_rejected() -> None:
    with pytest.raises(TranscriptParseError) as exc:
        parse_transcript(b"PK\x03\x04binary-zip", filename="x.srt")
    assert exc.value.code == "INVALID_TRANSCRIPT_TYPE"


def test_strip_presentation_markup_removes_tags() -> None:
    assert strip_presentation_markup('<script>alert(1)</script>Hello <b>there</b>') == (
        "alert(1) Hello there"
    )


def test_character_cap_enforced() -> None:
    raw = ("x" * 101).encode()
    with pytest.raises(TranscriptParseError) as exc:
        parse_transcript(raw, filename="big.txt", max_characters=100)
    assert exc.value.code == "TRANSCRIPT_TOO_LARGE"
