"""Deterministic offline text adapter — zero credentials, no network."""

from __future__ import annotations

from typing import Any

from app.ai.contracts import (
    FAKE_GROUNDED_QA,
    FAKE_VIDEO_SUMMARY,
    ModelCapabilities,
    ModelRequest,
    ModelResult,
    ModelUsage,
    RecordedRequest,
)
from app.ai.schema_parse import validate_against_schema


class FakeTextAdapter:
    provider = "fake"

    def __init__(self, model: str = "fake-chat-v1") -> None:
        self.model = model
        self.capabilities = ModelCapabilities(
            supports_json_schema=True,
            supports_stream=False,
            supports_vision=False,
            supports_batch=False,
            max_context_tokens=32_000,
        )
        self.recorded: list[RecordedRequest] = []

    async def generate_structured(self, request: ModelRequest) -> ModelResult:
        evidence_ids = [
            str(item.get("id") or item.get("segment_id") or "")
            for item in request.evidence
            if item.get("id") or item.get("segment_id")
        ]
        self.recorded.append(
            RecordedRequest(
                purpose=request.purpose,
                prompt_version=request.prompt_version,
                evidence_ids=evidence_ids,
                schema_keys=sorted(request.response_schema.get("properties", {}).keys())
                if isinstance(request.response_schema.get("properties"), dict)
                else sorted(request.response_schema.keys()),
            )
        )
        payload = self._fixture_for(request.purpose)
        parsed = validate_against_schema(payload, request.response_schema, provider=self.provider)
        return ModelResult(
            parsed=parsed,
            usage=ModelUsage(
                input_tokens=len(request.user_input.split()),
                output_tokens=len(str(parsed).split()),
                provider=self.provider,
                model=self.model,
                request_id="fake-req",
                tokens_estimated=True,
            ),
            raw_text=None,
        )

    def _fixture_for(self, purpose: str) -> dict[str, Any]:
        if purpose == "grounded_qa":
            return dict(FAKE_GROUNDED_QA)
        if purpose in {"video_summary", "playlist_summary"}:
            return dict(FAKE_VIDEO_SUMMARY)
        # Generic fixture — still marked as fixture data, not YouTube content.
        return {
            "result": "fixture_data",
            "purpose": purpose,
            "origin": "fixture_data",
        }

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.provider, "model": self.model}
