"""Deterministic eval metrics — no paid model judges."""

from __future__ import annotations

from collections.abc import Sequence


def attribution_precision(
    claim_text: str,
    cited_source_texts: Sequence[str],
) -> float:
    """
    Offline attribution proxy: fraction of claim content tokens that appear in
    at least one cited source segment. Not human entailment — calibrated gate only.
    """
    claim_tokens = _content_tokens(claim_text)
    if not claim_tokens:
        return 1.0
    source_tokens: set[str] = set()
    for blob in cited_source_texts:
        source_tokens.update(_content_tokens(blob))
    if not source_tokens:
        return 0.0
    hits = sum(1 for token in claim_tokens if token in source_tokens)
    return hits / len(claim_tokens)


def hybrid_mrr_lift(*, hybrid_mrr: float, dense_mrr: float) -> float:
    """Relative MRR lift of hybrid over dense-only (can be negative)."""
    return float(hybrid_mrr) - float(dense_mrr)


def recall_at_k(relevant: Sequence[str], retrieved: Sequence[str], *, k: int) -> float:
    if not relevant:
        return 1.0
    top = list(retrieved)[: max(1, k)]
    hits = sum(1 for item in relevant if item in top)
    return hits / len(relevant)


def mean_reciprocal_rank(relevant: Sequence[str], retrieved: Sequence[str]) -> float:
    if not relevant:
        return 1.0
    relevant_set = set(relevant)
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant_set:
            return 1.0 / float(rank)
    return 0.0


def phrase_hit_rate(text: str, phrases: Sequence[str]) -> float:
    if not phrases:
        return 1.0
    lowered = text.lower()
    hits = sum(1 for phrase in phrases if phrase.lower() in lowered)
    return hits / len(phrases)


def concept_coverage(text: str, concepts: Sequence[str]) -> float:
    return phrase_hit_rate(text, concepts)


def faithfulness_overlap(summary: str, source_texts: Sequence[str]) -> float:
    """
    Proxy faithfulness: fraction of summary content words that appear in sources.

    Not a semantic entailment score — documented as an offline proxy until calibrated.
    """
    source_tokens = set()
    for blob in source_texts:
        source_tokens.update(_content_tokens(blob))
    summary_tokens = _content_tokens(summary)
    if not summary_tokens:
        return 0.0
    if not source_tokens:
        return 0.0
    overlap = sum(1 for token in summary_tokens if token in source_tokens)
    return overlap / len(summary_tokens)


def estimate_tokens(text: str) -> int:
    parts = text.split()
    return max(1, len(parts)) if text.strip() else 0


def estimate_cost_usd(*, input_tokens: int, output_tokens: int) -> float:
    """
    Offline cost estimate using a fixed fake-provider rate card.

    Not a live billing quote — used only for relative baseline comparisons.
    """
    # $0.50 / 1M input, $1.50 / 1M output (illustrative fake rate)
    return (input_tokens * 0.50 + output_tokens * 1.50) / 1_000_000.0


def _content_tokens(text: str) -> list[str]:
    stop = {
        "a",
        "an",
        "the",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "is",
        "are",
        "be",
        "as",
        "with",
        "by",
        "from",
        "that",
        "this",
        "it",
        "you",
        "your",
    }
    tokens: list[str] = []
    normalized = text.lower()
    for ch in ",.()[]{}\"'`:;/\\":
        normalized = normalized.replace(ch, " ")
    for raw in normalized.split():
        token = "".join(c for c in raw if c.isalnum() or c in {"_", "-"})
        if len(token) < 3 or token in stop:
            continue
        tokens.append(token)
    return tokens
