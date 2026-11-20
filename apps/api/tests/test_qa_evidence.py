"""Grounded-QA evidence gate — invented citations rejected."""

from __future__ import annotations

import uuid

from app.domain.evidence import (
    QaEvidenceItem,
    build_qa_packet,
    validate_qa_payload,
)
from app.domain.qa_schemas import REFUSAL_MESSAGE


def _item(sid: str | None = None) -> QaEvidenceItem:
    return QaEvidenceItem(
        segment_id=sid or str(uuid.uuid4()),
        video_id=uuid.uuid4(),
        text="Ask clarifying questions before you respond.",
        start_ms=4500,
        end_ms=8000,
        source_revision=1,
        youtube_video_id="dQw4w9WgXcQ",
        video_title="Fixture lecture",
        timecode_quality="original",
    )


def test_invented_citation_rejected() -> None:
    good = _item()
    packet = build_qa_packet(
        workspace_id=uuid.uuid4(),
        scope_kind="video",
        scope_id=uuid.uuid4(),
        items=[good],
    )
    invented = str(uuid.uuid4())
    validated = validate_qa_payload(
        {
            "answer": "Hallucinated claim [1].",
            "claims": [
                {
                    "text": "Invented fact.",
                    "citation_segment_ids": [invented],
                }
            ],
            "unsupported": False,
            "confidence_label": "supported",
        },
        packet,
        refusal_message=REFUSAL_MESSAGE,
    )
    assert validated.refused is True
    assert validated.unsupported is True
    assert validated.claims == []
    assert invented in validated.dropped_citation_ids
    assert "enough verified" in validated.answer.lower() or "evidence" in validated.answer.lower()


def test_supported_claim_kept() -> None:
    good = _item()
    packet = build_qa_packet(
        workspace_id=uuid.uuid4(),
        scope_kind="video",
        scope_id=uuid.uuid4(),
        items=[good],
    )
    validated = validate_qa_payload(
        {
            "answer": "Ask clarifying questions [1].",
            "claims": [
                {
                    "text": "Ask clarifying questions.",
                    "citation_segment_ids": [good.segment_id],
                }
            ],
            "unsupported": False,
            "confidence_label": "supported",
            "analogies": [
                {
                    "text": "Like checking a recipe.",
                    "origin": "ai_generated_illustration",
                }
            ],
        },
        packet,
        refusal_message=REFUSAL_MESSAGE,
    )
    assert validated.refused is False
    assert validated.claims[0]["citation_segment_ids"] == [good.segment_id]
    assert validated.analogies[0]["origin"] == "ai_generated_illustration"


def test_empty_packet_refuses() -> None:
    packet = build_qa_packet(
        workspace_id=uuid.uuid4(),
        scope_kind="video",
        scope_id=uuid.uuid4(),
        items=[],
    )
    validated = validate_qa_payload(
        {
            "answer": "Something.",
            "claims": [{"text": "x", "citation_segment_ids": ["seg"]}],
            "unsupported": False,
            "confidence_label": "supported",
        },
        packet,
        refusal_message=REFUSAL_MESSAGE,
    )
    assert validated.refused is True
    assert validated.answer == REFUSAL_MESSAGE
