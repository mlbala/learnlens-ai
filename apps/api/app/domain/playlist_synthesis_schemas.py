"""Typed playlist / course synthesis schemas (Pydantic v2 + JSON Schema)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PLAYLIST_SYNTHESIS_PROMPT_VERSION = "playlist-synthesis-prompts-v1"
PLAYLIST_SUMMARY_KIND = "course"


class PlaylistTakeaway(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    source_video_ids: list[str] = Field(default_factory=list, max_length=40)
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=40)
    provenance: Literal[
        "source_supported",
        "ai_generated_illustration",
        "inference_or_interpretation",
        "not_covered",
    ] = "source_supported"


class TopicModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=4000)
    video_ids: list[str] = Field(default_factory=list, max_length=40)
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=80)


class LearningMapNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=300)
    video_ids: list[str] = Field(default_factory=list, max_length=40)
    order: int = Field(default=0, ge=0, le=10_000)


class CrossVideoConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    video_ids: list[str] = Field(default_factory=list, max_length=40)
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=40)


class RedundantTopicGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=300)
    video_ids: list[str] = Field(default_factory=list, max_length=40)
    note: str = Field(default="", max_length=1000)


class PlaylistSynthesisPayload(BaseModel):
    """Provider-facing course-level synthesis over ready per-video summaries only."""

    model_config = ConfigDict(extra="forbid")

    overview: str = Field(min_length=1, max_length=12_000)
    topic_modules: list[TopicModule] = Field(default_factory=list, max_length=40)
    learning_map: list[LearningMapNode] = Field(default_factory=list, max_length=80)
    cross_video_concepts: list[CrossVideoConcept] = Field(default_factory=list, max_length=40)
    redundant_topics: list[RedundantTopicGroup] = Field(default_factory=list, max_length=40)
    key_takeaways: list[PlaylistTakeaway] = Field(default_factory=list, max_length=60)
    origin: str = "model"


PLAYLIST_SYNTHESIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "overview",
        "topic_modules",
        "learning_map",
        "cross_video_concepts",
        "redundant_topics",
        "key_takeaways",
        "origin",
    ],
    "properties": {
        "overview": {"type": "string"},
        "topic_modules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "summary", "video_ids", "evidence_segment_ids"],
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "video_ids": {"type": "array", "items": {"type": "string"}},
                    "evidence_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "learning_map": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "video_ids", "order"],
                "properties": {
                    "label": {"type": "string"},
                    "video_ids": {"type": "array", "items": {"type": "string"}},
                    "order": {"type": "integer"},
                },
            },
        },
        "cross_video_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "description",
                    "video_ids",
                    "evidence_segment_ids",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "video_ids": {"type": "array", "items": {"type": "string"}},
                    "evidence_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "redundant_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["topic", "video_ids", "note"],
                "properties": {
                    "topic": {"type": "string"},
                    "video_ids": {"type": "array", "items": {"type": "string"}},
                    "note": {"type": "string"},
                },
            },
        },
        "key_takeaways": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "text",
                    "source_video_ids",
                    "evidence_segment_ids",
                    "provenance",
                ],
                "properties": {
                    "text": {"type": "string"},
                    "source_video_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "evidence_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "provenance": {"type": "string"},
                },
            },
        },
        "origin": {"type": "string"},
    },
}
