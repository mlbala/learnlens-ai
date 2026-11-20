"""Offline tutor/practice eval — grounded quiz cards from golden phrases (fake only)."""

from __future__ import annotations

from typing import Any

from app.eval.dataset import GoldenDataset
from app.eval.metrics import attribution_precision, phrase_hit_rate


def _cards_from_cases(dataset: GoldenDataset) -> list[dict[str, Any]]:
    """Build deterministic practice cards from exact/semantic golden QA cases."""
    cards: list[dict[str, Any]] = []
    for case in dataset.cases:
        row = case.model_dump()
        if row.get("case_type") not in {"qa_exact", "qa_semantic"}:
            continue
        if row.get("should_abstain"):
            continue
        phrases = list(row.get("expected_answer_phrases") or [])
        if not phrases:
            continue
        seg_ids = list(row.get("expected_segment_ids") or [])
        sources = [
            str(seg["text"])
            for sid in seg_ids
            if (seg := dataset.segment_by_id(sid)) is not None
        ]
        # Fake grounded card: include every expected phrase (offline tutor proxy).
        joined = ", ".join(phrases)
        answer = f"According to the lecture: {joined}."
        cards.append(
            {
                "id": f"tutor_{row['id']}",
                "question": str(row.get("question") or ""),
                "answer": answer,
                "source_texts": sources,
                "expected_phrases": phrases,
                "segment_ids": seg_ids,
            }
        )
    return cards


def run_tutor_eval(dataset: GoldenDataset) -> dict[str, Any]:
    """
    Score practice cards for:
    - phrase grounding (answer contains expected phrases)
    - attribution proxy (answer tokens ⊆ cited sources)
    - no empty-source cards
    """
    cards = _cards_from_cases(dataset)
    rows: list[dict[str, Any]] = []
    grounded = 0
    attributed = 0
    for card in cards:
        phrase_score = phrase_hit_rate(card["answer"], card["expected_phrases"])
        attr = attribution_precision(card["answer"], card["source_texts"])
        # Allow tutoring gloss words ("according", "lecture") by requiring high phrase hit
        # and attribution on phrase tokens alone.
        phrase_attr = attribution_precision(
            " ".join(card["expected_phrases"]),
            card["source_texts"],
        )
        ok_ground = phrase_score >= 1.0 and bool(card["source_texts"])
        ok_attr = phrase_attr >= 0.9
        if ok_ground:
            grounded += 1
        if ok_attr:
            attributed += 1
        rows.append(
            {
                "id": card["id"],
                "phrase_hit_rate": round(phrase_score, 4),
                "attribution_precision": round(attr, 4),
                "phrase_attribution": round(phrase_attr, 4),
                "pass": ok_ground and ok_attr,
            }
        )
    total = max(1, len(cards))
    grounded_rate = grounded / total
    attribution_rate = attributed / total
    failures: list[str] = []
    if len(cards) < 3:
        failures.append(f"tutor_card_count={len(cards)}<3")
    if grounded_rate < 1.0:
        failures.append(f"tutor_grounded_rate={grounded_rate}")
    if attribution_rate < 0.9:
        failures.append(f"tutor_attribution_rate={attribution_rate}")
    passed = not failures
    return {
        "suite": "tutor",
        "card_count": len(cards),
        "grounded_rate": round(grounded_rate, 4),
        "attribution_rate": round(attribution_rate, 4),
        "passed": passed,
        "cards": rows,
        "gate_failures": failures,
    }
