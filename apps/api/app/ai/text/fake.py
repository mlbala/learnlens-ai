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
        # Malicious evidence must never alter adapter behavior / purpose routing.
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
        payload = self._fixture_for(request.purpose, evidence_ids)
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

    def _fixture_for(self, purpose: str, evidence_ids: list[str]) -> dict[str, Any]:
        if purpose == "grounded_qa":
            eid = evidence_ids[0] if evidence_ids else "seg_fixture_01"
            payload = dict(FAKE_GROUNDED_QA)
            payload["claims"] = [
                {
                    "text": "Clarify requirements before coding.",
                    "citation_segment_ids": [eid],
                }
            ]
            return payload

        if purpose in {
            "video_summary",
            "playlist_summary",
            "chunk_summary",
            "chapter_summary",
        }:
            return _summary_fixture(evidence_ids)

        # Generic fixture — still marked as fixture data, not YouTube content.
        return {
            "result": "fixture_data",
            "purpose": purpose,
            "origin": "fixture_data",
        }

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.provider, "model": self.model}


def _summary_fixture(evidence_ids: list[str]) -> dict[str, Any]:
    eid = evidence_ids[0] if evidence_ids else "seg_fixture_01"
    # Keep static FAKE_VIDEO_SUMMARY shape available for import sites, but prefer
    # request evidence IDs so citation validation succeeds offline.
    base = dict(FAKE_VIDEO_SUMMARY)
    return {
        "summary": base.get(
            "summary",
            "Fixture summary: active listening and clarifying questions.",
        ),
        "key_points": list(
            base.get("key_points") or ["Listen actively", "Ask clarifying questions"]
        ),
        "claims": [
            {
                "text": "Ask clarifying questions before you respond.",
                "evidence_segment_ids": [eid],
                "provenance": "source_supported",
            }
        ],
        "examples": [
            {
                "text": "In a code review, restate the requirement in your own words.",
                "origin": "ai_generated_illustration",
            }
        ],
        "evidence_segment_ids": [eid],
        "origin": "fixture_data",
    }
