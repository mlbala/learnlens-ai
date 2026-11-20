"""Deterministic transcript chunker — preserves immutable segment IDs and timing.

Token targets are starting defaults from docs/05 (500–900 tokens, 80–120 overlap).
Does not invent timestamps. Untimed segments keep start/end as None.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

PROCESSING_VERSION = "chunk-v1"

# Approximate token estimate: whitespace-separated words (deterministic, offline-safe).
TARGET_TOKENS_MIN = 500
TARGET_TOKENS_MAX = 900
OVERLAP_TOKENS = 100


@dataclass(frozen=True, slots=True)
class SegmentRef:
    """Minimal segment view for chunking (IDs are immutable once persisted)."""

    id: uuid.UUID
    ordinal: int
    text: str
    start_ms: int | None
    end_ms: int | None
    speaker: str | None = None
    content_hash: str = ""


@dataclass(frozen=True, slots=True)
class TextChunk:
    chunk_id: uuid.UUID
    ordinal: int
    text: str
    segment_ids: tuple[uuid.UUID, ...]
    start_ms: int | None
    end_ms: int | None
    content_hash: str
    processing_version: str
    token_estimate: int


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate (word count). Never calls a paid tokenizer."""
    parts = text.split()
    return max(1, len(parts)) if text.strip() else 0


def _timing_for(segments: list[SegmentRef]) -> tuple[int | None, int | None]:
    starts = [s.start_ms for s in segments if s.start_ms is not None]
    ends = [s.end_ms for s in segments if s.end_ms is not None]
    if not starts or not ends:
        return None, None
    return min(starts), max(ends)


def _chunk_hash(segment_ids: list[uuid.UUID], text: str) -> str:
    payload = "|".join(str(i) for i in segment_ids) + "\n" + text
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def chunk_segments(
    segments: list[SegmentRef] | tuple[SegmentRef, ...],
    *,
    target_min: int = TARGET_TOKENS_MIN,
    target_max: int = TARGET_TOKENS_MAX,
    overlap_tokens: int = OVERLAP_TOKENS,
    processing_version: str = PROCESSING_VERSION,
) -> list[TextChunk]:
    """
    Partition ordered segments into overlapping contiguous chunks.

    Prefers boundaries at pauses (time gaps), speaker changes, or paragraph breaks
    once the running total reaches target_min. Hard-splits at target_max.
    """
    ordered = sorted(segments, key=lambda s: s.ordinal)
    if not ordered:
        return []

    chunks: list[TextChunk] = []
    start_idx = 0
    chunk_ordinal = 0

    while start_idx < len(ordered):
        end_idx = start_idx
        running = 0
        while end_idx < len(ordered):
            seg_tokens = estimate_tokens(ordered[end_idx].text)
            next_total = running + seg_tokens
            if running > 0 and next_total > target_max:
                break
            running = next_total
            end_idx += 1
            if running >= target_min and end_idx < len(ordered):
                # Prefer a soft boundary when available.
                if _is_soft_boundary(ordered[end_idx - 1], ordered[end_idx]):
                    break
                if running >= target_max:
                    break

        if end_idx <= start_idx:
            end_idx = start_idx + 1

        window = ordered[start_idx:end_idx]
        text = " ".join(s.text for s in window).strip()
        seg_ids = [s.id for s in window]
        start_ms, end_ms = _timing_for(window)
        chunks.append(
            TextChunk(
                chunk_id=uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{processing_version}:{','.join(str(i) for i in seg_ids)}",
                ),
                ordinal=chunk_ordinal,
                text=text,
                segment_ids=tuple(seg_ids),
                start_ms=start_ms,
                end_ms=end_ms,
                content_hash=_chunk_hash(seg_ids, text),
                processing_version=processing_version,
                token_estimate=estimate_tokens(text),
            )
        )
        chunk_ordinal += 1

        if end_idx >= len(ordered):
            break

        # Overlap: walk back until ~overlap_tokens of content is covered.
        overlap = 0
        next_start = end_idx
        for i in range(end_idx - 1, start_idx - 1, -1):
            overlap += estimate_tokens(ordered[i].text)
            next_start = i
            if overlap >= overlap_tokens:
                break
        # Always advance so we never infinite-loop on tiny segments.
        start_idx = max(next_start, start_idx + 1)

    return chunks


def _is_soft_boundary(prev: SegmentRef, nxt: SegmentRef) -> bool:
    if prev.speaker and nxt.speaker and prev.speaker != nxt.speaker:
        return True
    if (
        prev.end_ms is not None
        and nxt.start_ms is not None
        and (nxt.start_ms - prev.end_ms) >= 2_500
    ):
        return True
    # Untimed: paragraph-ish break when previous ends with blank-line cue or heading.
    stripped = nxt.text.strip()
    if stripped.startswith("#") or (len(stripped) < 80 and stripped.endswith(":")):
        return True
    return False
