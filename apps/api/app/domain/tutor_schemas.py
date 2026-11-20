"""Structured tutor/quiz provider contracts (phase 18)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PresentationLanguage(StrEnum):
    EN = "en"
    TA = "ta"


class StudyItemKind(StrEnum):
    FLASHCARD = "flashcard"
    QUIZ = "quiz"


class ExplanationOrigin(StrEnum):
    SOURCE_SUPPORTED = "source_supported"
    AI_GENERATED_ILLUSTRATION = "ai_generated_illustration"


PROMPT_VERSION = "tutor-quiz-prompts-v1"

EFFICACY_DISCLAIMER = (
    "Practice counts only — no learning-efficacy claim without evaluation."
)


class TutorConceptDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=20)
    prerequisites: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Canonical names of prerequisite concepts in this payload.",
    )


class TutorItemDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_kind: Literal["flashcard", "quiz"]
    prompt: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=4000)
    explanation: str = Field(default="", max_length=4000)
    explanation_origin: Literal[
        "source_supported", "ai_generated_illustration"
    ] = "source_supported"
    choices: list[str] = Field(default_factory=list, max_length=6)
    correct_choice_index: int | None = None
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=20)
    concept_name: str | None = Field(default=None, max_length=200)
    presentation: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional en/ta presentation overlays; evidence remains original language.",
    )


class TutorDeckResponse(BaseModel):
    """Provider-facing structured deck — timestamps/URLs are never model-supplied."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    items: list[TutorItemDraft] = Field(default_factory=list, max_length=40)
    concepts: list[TutorConceptDraft] = Field(default_factory=list, max_length=20)
    origin: Literal["fixture_data", "ai_generated"] = "fixture_data"


TUTOR_DECK_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "items", "concepts", "origin"],
    "properties": {
        "title": {"type": "string"},
        "origin": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "item_kind",
                    "prompt",
                    "answer",
                    "explanation_origin",
                    "evidence_segment_ids",
                ],
                "properties": {
                    "item_kind": {"type": "string"},
                    "prompt": {"type": "string"},
                    "answer": {"type": "string"},
                    "explanation": {"type": "string"},
                    "explanation_origin": {"type": "string"},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "correct_choice_index": {"type": ["integer", "null"]},
                    "evidence_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "concept_name": {"type": ["string", "null"]},
                    "presentation": {"type": "object"},
                },
            },
        },
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "evidence_segment_ids"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "evidence_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "prerequisites": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
}
