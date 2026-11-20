"""Reciprocal Rank Fusion — local implementation for fake store + contract tests."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankedId:
    point_id: uuid.UUID
    rank: int  # zero-based
    source: str


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[uuid.UUID]],
    *,
    sources: Sequence[str],
    k: int = 2,
    limit: int = 12,
) -> list[tuple[uuid.UUID, float, tuple[str, ...]]]:
    """
    Fuse ranked ID lists with classic RRF: score = Σ 1/(k + rank).

    Returns (point_id, score, contributing_sources) sorted by score desc.
    """
    if len(rankings) != len(sources):
        raise ValueError("rankings and sources must have the same length")

    scores: dict[uuid.UUID, float] = {}
    contrib: dict[uuid.UUID, set[str]] = {}
    for ranking, source in zip(rankings, sources, strict=True):
        for rank, point_id in enumerate(ranking):
            scores[point_id] = scores.get(point_id, 0.0) + 1.0 / (k + rank)
            contrib.setdefault(point_id, set()).add(source)

    ordered = sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
    results: list[tuple[uuid.UUID, float, tuple[str, ...]]] = []
    for point_id, score in ordered[: max(1, limit)]:
        results.append((point_id, score, tuple(sorted(contrib.get(point_id, ())))))
    return results
