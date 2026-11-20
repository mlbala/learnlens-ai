"""Typed summary output schemas (Pydantic v2 + JSON Schema for providers)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SummaryKind(StrEnum):
    SHORT = "short"
    DETAILED = "detailed"
    SIMPLE = "simple"
    TECHNICAL = "technical"


class Provenance(StrEnum):
    SOURCE_SUPPORTED = "source_supported"
    AI_GENERATED_ILLUSTRATION = "ai_generated_illustration"
    INFERENCE_OR_INTERPRETATION = "inference_or_interpretation"
    NOT_COVERED = "not_covered"


PROMPT_VERSION = "summary-prompts-v1"


class SummaryClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    evidence_segment_ids: list[str] = Field(default_factory=list)
    provenance: Literal[
        "source_supported",
        "ai_generated_illustration",
        "inference_or_interpretation",
        "not_covered",
    ] = "source_supported"


class SummaryExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    origin: Literal["ai_generated_illustration", "source_supported"] = (
        "ai_generated_illustration"
    )


class StructuredSummary(BaseModel):
    """Provider-facing structured summary for chunk / chapter / video scopes."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=12_000)
    key_points: list[str] = Field(default_factory=list, max_length=40)
    claims: list[SummaryClaim] = Field(default_factory=list, max_length=80)
    examples: list[SummaryExample] = Field(default_factory=list, max_length=20)
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=200)
    origin: str = "model"


SUMMARY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "summary",
        "key_points",
        "claims",
        "examples",
        "evidence_segment_ids",
        "origin",
    ],
    "properties": {
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "evidence_segment_ids", "provenance"],
                "properties": {
                    "text": {"type": "string"},
                    "evidence_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "provenance": {"type": "string"},
                },
            },
        },
        "examples": {
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
        "evidence_segment_ids": {"type": "array", "items": {"type": "string"}},
        "origin": {"type": "string"},
    },
}


CHAPTER_TOPIC_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "chapter_title",
        "start_segment_id",
        "end_segment_id",
        "key_claims",
        "examples",
    ],
    "properties": {
        "chapter_title": {"type": "string"},
        "start_segment_id": {"type": "string"},
        "end_segment_id": {"type": "string"},
        "key_claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["claim", "evidence_segment_ids"],
                "properties": {
                    "claim": {"type": "string"},
                    "evidence_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "examples": {
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
