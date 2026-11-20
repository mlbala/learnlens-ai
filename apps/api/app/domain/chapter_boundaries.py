"""Chapter boundary detection with deterministic fallback.

Prefers semantic/topic cues (time gaps, speaker changes, heading-like lines).
Falls back to bounded contiguous groups — never arbitrary fixed clock splits alone.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.chunking import SegmentRef, TextChunk, estimate_tokens

# Soft chapter target (~3–8 minutes of speech when timed; else ~token budget).
_GAP_MS = 4_000
_FALLBACK_TOKEN_TARGET = 1_800
_MIN_SEGMENTS_PER_CHAPTER = 1


@dataclass(frozen=True, slots=True)
class ChapterBoundary:
    title: str
    start_segment_id: uuid.UUID
    end_segment_id: uuid.UUID
    segment_ids: tuple[uuid.UUID, ...]
    chunk_ordinals: tuple[int, ...]
    topic_json: dict


def detect_chapter_boundaries(
    segments: list[SegmentRef] | tuple[SegmentRef, ...],
    chunks: list[TextChunk] | tuple[TextChunk, ...] | None = None,
) -> list[ChapterBoundary]:
    """Return ordered chapter spans covering all segments exactly once."""
    ordered = sorted(segments, key=lambda s: s.ordinal)
    if not ordered:
        return []

    break_after: set[int] = set()  # segment ordinals after which a chapter ends

    for i in range(len(ordered) - 1):
        cur, nxt = ordered[i], ordered[i + 1]
        if cur.speaker and nxt.speaker and cur.speaker != nxt.speaker:
            break_after.add(cur.ordinal)
            continue
        if (
            cur.end_ms is not None
            and nxt.start_ms is not None
            and (nxt.start_ms - cur.end_ms) >= _GAP_MS
        ):
            break_after.add(cur.ordinal)
            continue
        if _looks_like_heading(nxt.text):
            break_after.add(cur.ordinal)

    # Deterministic fallback: if no (or too few) semantic breaks, split by token budget.
    if len(break_after) == 0 and len(ordered) > 1:
        running = 0
        for seg in ordered[:-1]:
            running += estimate_tokens(seg.text)
            if running >= _FALLBACK_TOKEN_TARGET:
                break_after.add(seg.ordinal)
                running = 0

    groups: list[list[SegmentRef]] = []
    current: list[SegmentRef] = []
    for seg in ordered:
        current.append(seg)
        if seg.ordinal in break_after and len(current) >= _MIN_SEGMENTS_PER_CHAPTER:
            groups.append(current)
            current = []
    if current:
        if groups and len(current) < _MIN_SEGMENTS_PER_CHAPTER:
            groups[-1].extend(current)
        else:
            groups.append(current)

    chunk_list = list(chunks or [])
    chapters: list[ChapterBoundary] = []
    for idx, group in enumerate(groups):
        title = _title_for(group, idx)
        seg_ids = tuple(s.id for s in group)
        chunk_ords = tuple(
            c.ordinal
            for c in chunk_list
            if any(sid in c.segment_ids for sid in seg_ids)
        )
        chapters.append(
            ChapterBoundary(
                title=title,
                start_segment_id=group[0].id,
                end_segment_id=group[-1].id,
                segment_ids=seg_ids,
                chunk_ordinals=chunk_ords,
                topic_json={
                    "strategy": "semantic_or_fallback",
                    "segment_count": len(group),
                    "origin": "fixture_or_heuristic",
                },
            )
        )
    return chapters


def _looks_like_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return True
    if len(stripped) <= 72 and stripped.endswith(":") and " " in stripped:
        return True
    return False


def _title_for(group: list[SegmentRef], index: int) -> str:
    first = group[0].text.strip()
    if _looks_like_heading(first):
        return first.lstrip("#").strip().rstrip(":")[:120] or f"Chapter {index + 1}"
    # Use a short prefix of the first segment — not fabricated YouTube titles.
    words = first.split()
    preview = " ".join(words[:8]).strip()
    if preview:
        return preview[:120]
    return f"Chapter {index + 1}"
