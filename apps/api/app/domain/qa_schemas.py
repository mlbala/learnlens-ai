"""Structured grounded-QA schemas (provider contract + explanation styles)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExplanationMode(StrEnum):
    SIMPLE = "simple"
    STANDARD = "standard"
    TECHNICAL = "technical"


PROMPT_VERSION = "grounded-qa-prompts-v1"

REFUSAL_MESSAGE = (
    "I do not have enough verified transcript evidence in this scope to answer that. "
    "Upload or index authorized source material that covers the topic, then ask again."
)


class QaClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    citation_segment_ids: list[str] = Field(default_factory=list, max_length=40)


class QaAnalogy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    origin: Literal["ai_generated_illustration"] = "ai_generated_illustration"


class GroundedQaResponse(BaseModel):
    """Provider-facing structured answer — timestamps/URLs are never model-supplied."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=12_000)
    claims: list[QaClaim] = Field(default_factory=list, max_length=40)
    unsupported: bool = False
    confidence_label: Literal["supported", "partial", "unsupported", "abstain"] = "supported"
    analogies: list[QaAnalogy] = Field(default_factory=list, max_length=5)


GROUNDED_QA_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["answer", "claims", "unsupported", "confidence_label"],
    "properties": {
        "answer": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "citation_segment_ids"],
                "properties": {
                    "text": {"type": "string"},
                    "citation_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "unsupported": {"type": "boolean"},
        "confidence_label": {"type": "string"},
        "analogies": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "origin"],
                "properties": {
                    "text": {"type": "string"},
                    "origin": {"type": "string"},
                },
            },
        },
    },
}
