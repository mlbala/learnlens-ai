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
        payload = self._fixture_for(request)
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

    def _fixture_for(self, request: ModelRequest) -> dict[str, Any]:
        purpose = request.purpose
        evidence_ids = [
            str(item.get("id") or item.get("segment_id") or "")
            for item in request.evidence
            if item.get("id") or item.get("segment_id")
        ]
        if purpose == "grounded_qa":
            if not evidence_ids:
                return {
                    "answer": (
                        "I do not have enough verified transcript evidence in this "
                        "scope to answer that."
                    ),
                    "claims": [],
                    "unsupported": True,
                    "confidence_label": "abstain",
                    "analogies": [],
                }
            eid = evidence_ids[0]
            payload = dict(FAKE_GROUNDED_QA)
            payload["claims"] = [
                {
                    "text": "Clarify requirements before coding.",
                    "citation_segment_ids": [eid],
                }
            ]
            payload["analogies"] = [
                {
                    "text": "Like checking a recipe before cooking.",
                    "origin": "ai_generated_illustration",
                }
            ]
            return payload

        if purpose == "playlist_summary":
            return _playlist_summary_fixture(request.evidence)

        if purpose in {
            "video_summary",
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


def _playlist_summary_fixture(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Course synthesis fixture — cites only included video/segment IDs from evidence."""
    video_ids: list[str] = []
    segment_ids: list[str] = []
    for item in evidence:
        vid = str(item.get("video_id") or "")
        if vid and vid not in video_ids:
            video_ids.append(vid)
        for sid in item.get("evidence_segment_ids") or []:
            s = str(sid)
            if s and s not in segment_ids:
                segment_ids.append(s)
        fallback = str(item.get("id") or item.get("segment_id") or "")
        if fallback and fallback not in segment_ids:
            segment_ids.append(fallback)

    if not video_ids:
        video_ids = ["video_fixture_01"]
    if not segment_ids:
        segment_ids = ["seg_fixture_01"]

    primary_vid = video_ids[0]
    primary_seg = segment_ids[0]
    modules = [
        {
            "title": "Fixture module: Communication foundations",
            "summary": "Fixture overview of active listening across included lessons.",
            "video_ids": list(video_ids),
            "evidence_segment_ids": [primary_seg],
        }
    ]
    learning_map = [
        {
            "label": f"Lesson {idx + 1}",
            "video_ids": [vid],
            "order": idx,
        }
        for idx, vid in enumerate(video_ids)
    ]
    concepts = [
        {
            "name": "Clarifying questions",
            "description": "Fixture cross-video concept present in included lessons only.",
            "video_ids": list(video_ids),
            "evidence_segment_ids": [primary_seg],
        }
    ]
    redundant = (
        [
            {
                "topic": "Active listening",
                "video_ids": list(video_ids[:2]),
                "note": "Fixture redundant-topic grouping across ready lessons.",
            }
        ]
        if len(video_ids) >= 2
        else []
    )
    takeaways = [
        {
            "text": "Ask clarifying questions before you respond.",
            "source_video_ids": [primary_vid],
            "evidence_segment_ids": [primary_seg],
            "provenance": "source_supported",
        }
    ]
    return {
        "overview": (
            f"Fixture course overview based on {len(video_ids)} ready lesson(s). "
            "Missing lessons are not invented."
        ),
        "topic_modules": modules,
        "learning_map": learning_map,
        "cross_video_concepts": concepts,
        "redundant_topics": redundant,
        "key_takeaways": takeaways,
        "origin": "fixture_data",
    }
