"""Provider-neutral text and embedding contracts (phase 03)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ModelCapabilities:
    """Feature flags exposed to settings/UI — no provider-specific knobs."""

    supports_json_schema: bool
    supports_stream: bool
    supports_vision: bool
    supports_batch: bool
    max_context_tokens: int


@dataclass(frozen=True)
class ModelRequest:
    purpose: str  # video_summary|playlist_summary|grounded_qa
    instructions: str
    user_input: str
    evidence: list[dict[str, Any]]
    response_schema: dict[str, Any]
    max_output_tokens: int
    temperature: float
    timeout_seconds: int
    prompt_version: str


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None
    output_tokens: int | None
    provider: str
    model: str
    request_id: str | None
    tokens_estimated: bool = False


@dataclass(frozen=True)
class ModelResult:
    parsed: dict[str, Any]
    usage: ModelUsage
    raw_text: str | None = None


@dataclass
class TextAdapterInfo:
    provider: str
    model: str
    capabilities: ModelCapabilities
    key_configured: bool


@dataclass
class EmbeddingAdapterInfo:
    provider: str
    model: str
    profile_id: str
    dimensions: int
    capabilities: ModelCapabilities
    key_configured: bool


@runtime_checkable
class TextModel(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def capabilities(self) -> ModelCapabilities: ...

    async def generate_structured(self, request: ModelRequest) -> ModelResult: ...

    async def health(self) -> dict[str, str]: ...


@runtime_checkable
class EmbeddingModel(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def profile_id(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    @property
    def capabilities(self) -> ModelCapabilities: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...

    async def health(self) -> dict[str, str]: ...


# Deterministic fixture schemas used by FakeTextAdapter (not live YouTube content).
FAKE_GROUNDED_QA: dict[str, Any] = {
    "answer": "Clarify requirements before coding [1].",
    "claims": [
        {
            "text": "Clarify requirements before coding.",
            "citation_segment_ids": ["seg_fixture_01"],
        }
    ],
    "unsupported": False,
    "confidence_label": "supported",
}

FAKE_VIDEO_SUMMARY: dict[str, Any] = {
    "summary": "Fixture summary: active listening and clarifying questions.",
    "key_points": ["Listen actively", "Ask clarifying questions"],
    "claims": [
        {
            "text": "Ask clarifying questions before you respond.",
            "evidence_segment_ids": ["seg_fixture_01"],
            "provenance": "source_supported",
        }
    ],
    "examples": [
        {
            "text": "In a code review, restate the requirement in your own words.",
            "origin": "ai_generated_illustration",
        }
    ],
    "evidence_segment_ids": ["seg_fixture_01"],
    "origin": "fixture_data",
}


@dataclass
class RecordedRequest:
    """Captured request shape for fake adapters (tests / debug without network)."""

    purpose: str
    prompt_version: str
    evidence_ids: list[str] = field(default_factory=list)
    schema_keys: list[str] = field(default_factory=list)
