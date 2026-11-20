"""Tutor/quiz prompt builders — evidence treated as untrusted data."""

from __future__ import annotations

from typing import Any

from app.domain.tutor_schemas import PROMPT_VERSION, PresentationLanguage


def prompt_version() -> str:
    return PROMPT_VERSION


def instructions_for(*, presentation_language: PresentationLanguage) -> str:
    lang = presentation_language.value
    return (
        "Generate source-grounded flashcards and quiz questions from the evidence "
        "packet only. Every source-supported claim must cite evidence_segment_ids "
        "from the packet. Explanations not present in the source must use "
        "explanation_origin=ai_generated_illustration and must not be presented as "
        "instructor speech. Do not invent timestamps or YouTube URLs. "
        f"Presentation language preference is '{lang}' for optional overlays in "
        "item.presentation; keep evidence text in its original language. "
        "Never claim measured learning gains. Mark origin as fixture_data when "
        "using synthetic fixtures."
    )


def user_input_for(*, video_title: str, presentation_language: str) -> str:
    return (
        f"Create a practice deck for video '{video_title}'. "
        f"Preferred presentation language: {presentation_language}. "
        "Include flashcards and multiple-choice quiz items with concept "
        "prerequisite links where supported by evidence."
    )


def wrap_evidence_items(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize segment rows into model evidence items (untrusted content)."""
    out: list[dict[str, Any]] = []
    for seg in segments:
        sid = str(seg.get("id") or seg.get("segment_id") or "")
        if not sid:
            continue
        out.append(
            {
                "id": sid,
                "segment_id": sid,
                "text": str(seg.get("text") or "")[:2000],
                "ordinal": seg.get("ordinal"),
                "start_ms": seg.get("start_ms"),
                "end_ms": seg.get("end_ms"),
            }
        )
    return out
