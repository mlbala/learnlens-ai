"""Provider-neutral speech-to-text and vision contracts (phase 17).

Separate from text/embedding adapters. Real vendor adapters stay out of default
offline paths — only fake/fixture adapters run without operator opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class MediaCue:
    """One derived speech cue. Timing is only set when alignment is verified."""

    ordinal: int
    text: str
    start_ms: int | None
    end_ms: int | None
    alignment_confidence: float
    provenance: str  # speech_to_text | vision_ocr | fixture_data


@dataclass(frozen=True, slots=True)
class MediaFrameDesc:
    """One extracted visual frame/diagram description with time anchor."""

    ordinal: int
    timestamp_ms: int | None
    description: str
    frame_kind: str  # frame | diagram | slide
    alignment_confidence: float
    provenance: str
    # Relative payload for private storage (fake: empty bytes marker).
    frame_bytes: bytes


@dataclass(frozen=True, slots=True)
class SpeechToTextResult:
    cues: tuple[MediaCue, ...]
    provider: str
    model: str
    estimated_cpu_units: float
    estimated_cost_usd: float


@dataclass(frozen=True, slots=True)
class VisionExtractResult:
    frames: tuple[MediaFrameDesc, ...]
    provider: str
    model: str
    estimated_cpu_units: float
    estimated_cost_usd: float


@runtime_checkable
class SpeechToTextModel(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def transcribe(
        self,
        *,
        media_bytes: bytes,
        media_kind: str,
        content_hash: str,
        max_duration_ms: int,
    ) -> SpeechToTextResult: ...


@runtime_checkable
class VisionExtractModel(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def extract_frames(
        self,
        *,
        media_bytes: bytes,
        media_kind: str,
        content_hash: str,
        max_frames: int,
    ) -> VisionExtractResult: ...


# Deterministic fixture captions — synthetic authorized media only (not YouTube).
FIXTURE_SPEECH_CUES: tuple[dict[str, Any], ...] = (
    {
        "ordinal": 1,
        "text": "Fixture media: welcome to the authorized audio lesson.",
        "start_ms": 0,
        "end_ms": 2500,
        "alignment_confidence": 0.96,
        "provenance": "fixture_data",
    },
    {
        "ordinal": 2,
        "text": "Ask clarifying questions before you respond.",
        "start_ms": 2500,
        "end_ms": 5200,
        "alignment_confidence": 0.91,
        "provenance": "fixture_data",
    },
    {
        "ordinal": 3,
        "text": "Uncertain timing example without verified anchors.",
        "start_ms": None,
        "end_ms": None,
        "alignment_confidence": 0.35,
        "provenance": "fixture_data",
    },
)

FIXTURE_FRAMES: tuple[dict[str, Any], ...] = (
    {
        "ordinal": 1,
        "timestamp_ms": 1000,
        "description": "Fixture slide: Active listening checklist (synthetic).",
        "frame_kind": "slide",
        "alignment_confidence": 0.88,
        "provenance": "fixture_data",
    },
    {
        "ordinal": 2,
        "timestamp_ms": None,
        "description": "Uncertain diagram region — timing not verified.",
        "frame_kind": "diagram",
        "alignment_confidence": 0.28,
        "provenance": "fixture_data",
    },
)
