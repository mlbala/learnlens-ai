"""Evidence gate for tutor/quiz payloads — fail closed on unsupported IDs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.tutor_schemas import TutorDeckResponse, TutorItemDraft


class TutorValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ValidatedTutorDeck:
    title: str
    items: list[dict[str, Any]]
    concepts: list[dict[str, Any]]
    origin: str
    dropped_citation_ids: list[str] = field(default_factory=list)
    blocked_unsupported: bool = False


def _filter_ids(
    raw: list[Any] | None,
    allowed: frozenset[str],
    dropped: list[str],
) -> list[str]:
    kept: list[str] = []
    for item in raw or []:
        sid = str(item)
        if sid in allowed:
            if sid not in kept:
                kept.append(sid)
        else:
            dropped.append(sid)
    return kept


def validate_tutor_payload(
    payload: dict[str, Any],
    *,
    allowed_segment_ids: frozenset[str] | set[str],
) -> ValidatedTutorDeck:
    """
    Keep only items whose source-supported evidence resolves to the packet.

    Quiz/flashcard items with no remaining evidence are dropped. AI illustrations
    may keep explanation_origin=ai_generated_illustration but still require at
    least one verified evidence ID for the source-backed prompt/answer.
    """
    allowed = frozenset(str(i) for i in allowed_segment_ids if i)
    dropped: list[str] = []

    try:
        parsed = TutorDeckResponse.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 — map to domain error
        raise TutorValidationError(
            "TUTOR_SCHEMA_INVALID",
            f"Tutor payload failed schema validation: {exc}",
        ) from exc

    concepts_out: list[dict[str, Any]] = []
    for concept in parsed.concepts:
        eids = _filter_ids(list(concept.evidence_segment_ids), allowed, dropped)
        if not eids:
            continue
        concepts_out.append(
            {
                "name": concept.name.strip(),
                "description": concept.description.strip(),
                "evidence_segment_ids": eids,
                "prerequisites": [
                    p.strip() for p in concept.prerequisites if str(p).strip()
                ],
            }
        )

    items_out: list[dict[str, Any]] = []
    for item in parsed.items:
        eids = _filter_ids(list(item.evidence_segment_ids), allowed, dropped)
        if not eids:
            continue
        origin = item.explanation_origin
        if origin not in {"source_supported", "ai_generated_illustration"}:
            origin = "ai_generated_illustration"

        choices = [str(c).strip() for c in item.choices if str(c).strip()]
        correct = item.correct_choice_index
        if item.item_kind == "quiz":
            if len(choices) < 2:
                continue
            if correct is None or correct < 0 or correct >= len(choices):
                continue
        else:
            choices = []
            correct = None

        presentation = _sanitize_presentation(item.presentation)
        items_out.append(
            {
                "item_kind": item.item_kind,
                "prompt": item.prompt.strip(),
                "answer": item.answer.strip(),
                "explanation": (item.explanation or "").strip(),
                "explanation_origin": origin,
                "choices": choices,
                "correct_choice_index": correct,
                "evidence_segment_ids": eids,
                "concept_name": (item.concept_name or "").strip() or None,
                "presentation": presentation,
            }
        )

    blocked = not items_out and bool(parsed.items)
    return ValidatedTutorDeck(
        title=parsed.title.strip() or "Practice deck",
        items=items_out,
        concepts=concepts_out,
        origin=(
            parsed.origin
            if parsed.origin in {"fixture_data", "ai_generated"}
            else "fixture_data"
        ),
        dropped_citation_ids=dropped,
        blocked_unsupported=blocked,
    )


def _sanitize_presentation(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Keep en/ta presentation overlays only; never store invented timestamps."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for lang in ("en", "ta"):
        block = raw.get(lang)
        if not isinstance(block, dict):
            continue
        cleaned: dict[str, str] = {}
        for key in ("prompt", "answer", "explanation"):
            val = block.get(key)
            if isinstance(val, str) and val.strip():
                cleaned[key] = val.strip()[:4000]
        if cleaned:
            out[lang] = cleaned
    return out


def resolve_item_evidence(
    item: TutorItemDraft | dict[str, Any],
    *,
    allowed_segment_ids: frozenset[str] | set[str],
) -> tuple[list[str], bool]:
    """Return (resolved_ids, all_resolved) for an attempt / review display."""
    allowed = frozenset(str(i) for i in allowed_segment_ids if i)
    if isinstance(item, TutorItemDraft):
        raw_ids = list(item.evidence_segment_ids)
    else:
        raw_ids = list(item.get("evidence_segment_ids") or [])
    resolved = [sid for sid in (str(x) for x in raw_ids) if sid in allowed]
    all_ok = bool(resolved) and len(resolved) == len([str(x) for x in raw_ids if str(x)])
    return resolved, all_ok
