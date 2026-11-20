"""Deterministic chunker + chapter boundary unit tests (fixture data only)."""

from __future__ import annotations

import uuid

from app.domain.chapter_boundaries import detect_chapter_boundaries
from app.domain.chunking import SegmentRef, chunk_segments, estimate_tokens


def _seg(
    ordinal: int,
    text: str,
    *,
    start: int | None = None,
    end: int | None = None,
) -> SegmentRef:
    return SegmentRef(
        id=uuid.uuid4(),
        ordinal=ordinal,
        text=text,
        start_ms=start,
        end_ms=end,
        content_hash=f"h{ordinal}",
    )


def test_estimate_tokens_deterministic() -> None:
    assert estimate_tokens("one two three") == 3
    assert estimate_tokens("") == 0


def test_chunker_preserves_segment_ids_and_timing() -> None:
    # Build a long enough transcript to force multiple overlapping chunks.
    words = " ".join(f"word{i}" for i in range(400))
    segments = [
        _seg(0, words, start=0, end=10_000),
        _seg(1, words, start=10_000, end=20_000),
        _seg(2, words, start=22_500, end=32_000),  # gap → soft boundary
    ]
    chunks = chunk_segments(segments, target_min=50, target_max=450, overlap_tokens=40)
    assert len(chunks) >= 2
    all_ids = {s.id for s in segments}
    for chunk in chunks:
        assert chunk.segment_ids
        assert set(chunk.segment_ids) <= all_ids
        assert chunk.processing_version.startswith("chunk-")
        assert chunk.content_hash
        # Timing only when present on constituents.
        assert chunk.start_ms is not None
        assert chunk.end_ms is not None
        assert chunk.start_ms <= chunk.end_ms


def test_untimed_chunks_have_null_timing() -> None:
    segments = [_seg(0, "hello world " * 20), _seg(1, "more text " * 20)]
    chunks = chunk_segments(segments, target_min=5, target_max=40, overlap_tokens=5)
    assert chunks
    assert all(c.start_ms is None and c.end_ms is None for c in chunks)


def test_chapter_fallback_covers_all_segments() -> None:
    segments = [_seg(i, f"segment {i} content here") for i in range(6)]
    chapters = detect_chapter_boundaries(segments)
    assert chapters
    covered = [sid for ch in chapters for sid in ch.segment_ids]
    assert covered == [s.id for s in segments]


def test_chapter_splits_on_time_gap() -> None:
    segments = [
        _seg(0, "Intro talking", start=0, end=1000),
        _seg(1, "More intro", start=1000, end=2000),
        _seg(2, "New topic after pause", start=10_000, end=12_000),
    ]
    chapters = detect_chapter_boundaries(segments)
    assert len(chapters) >= 2
    assert chapters[0].end_segment_id == segments[1].id
    assert chapters[1].start_segment_id == segments[2].id
