"""Evidence validation — unsupported IDs dropped / blocked."""

from __future__ import annotations

import uuid

from app.domain.evidence import build_packet, validate_summary_payload


def test_drops_ids_outside_prompt_evidence() -> None:
    workspace = uuid.uuid4()
    video = uuid.uuid4()
    good = str(uuid.uuid4())
    bad = str(uuid.uuid4())
    packet = build_packet(
        workspace_id=workspace,
        video_id=video,
        source_revision=1,
        workspace_segment_ids={good, bad},
        prompt_evidence_ids={good},
    )
    validated = validate_summary_payload(
        {
            "summary": "Supported claim.",
            "key_points": ["one"],
            "claims": [
                {
                    "text": "ok",
                    "evidence_segment_ids": [good],
                    "provenance": "source_supported",
                },
                {
                    "text": "evil",
                    "evidence_segment_ids": [bad],
                    "provenance": "source_supported",
                },
            ],
            "examples": [
                {"text": "analogy", "origin": "ai_generated_illustration"},
            ],
            "evidence_segment_ids": [good, bad],
            "origin": "fixture_data",
        },
        packet,
    )
    assert validated.claims[0]["evidence_segment_ids"] == [good]
    assert all(c["text"] != "evil" for c in validated.claims)
    assert bad in validated.dropped_citation_ids
    assert good in validated.evidence_segment_ids
    assert bad not in validated.evidence_segment_ids


def test_blocks_when_all_source_claims_unsupported() -> None:
    workspace = uuid.uuid4()
    video = uuid.uuid4()
    packet = build_packet(
        workspace_id=workspace,
        video_id=video,
        source_revision=1,
        workspace_segment_ids={"seg-a"},
        prompt_evidence_ids={"seg-a"},
    )
    validated = validate_summary_payload(
        {
            "summary": "Hallucinated.",
            "key_points": ["x"],
            "claims": [
                {
                    "text": "not real",
                    "evidence_segment_ids": ["seg-missing"],
                    "provenance": "source_supported",
                }
            ],
            "examples": [],
            "evidence_segment_ids": ["seg-missing"],
            "origin": "model",
        },
        packet,
    )
    assert validated.blocked_unsupported is True
    assert "blocked" in validated.summary.lower()
    assert validated.claims == []
