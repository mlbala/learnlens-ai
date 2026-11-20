"""Unit tests for playlist synthesis evidence gating."""

from __future__ import annotations

from app.domain.playlist_synthesis_validate import validate_playlist_synthesis_payload


def test_drops_excluded_video_and_unknown_segment_claims() -> None:
    payload = {
        "overview": "Course overview",
        "topic_modules": [
            {
                "title": "Included module",
                "summary": "Ok",
                "video_ids": ["vid-a", "vid-excluded"],
                "evidence_segment_ids": ["seg-1", "seg-x"],
            }
        ],
        "learning_map": [
            {"label": "A", "video_ids": ["vid-a"], "order": 0},
            {"label": "Bad", "video_ids": ["vid-excluded"], "order": 1},
        ],
        "cross_video_concepts": [
            {
                "name": "Concept",
                "description": "Desc",
                "video_ids": ["vid-a"],
                "evidence_segment_ids": ["seg-1"],
            }
        ],
        "redundant_topics": [
            {
                "topic": "Dup",
                "video_ids": ["vid-a", "vid-excluded"],
                "note": "note",
            }
        ],
        "key_takeaways": [
            {
                "text": "Supported",
                "source_video_ids": ["vid-a"],
                "evidence_segment_ids": ["seg-1"],
                "provenance": "source_supported",
            },
            {
                "text": "Excluded only",
                "source_video_ids": ["vid-excluded"],
                "evidence_segment_ids": ["seg-1"],
                "provenance": "source_supported",
            },
            {
                "text": "No evidence",
                "source_video_ids": ["vid-a"],
                "evidence_segment_ids": ["seg-x"],
                "provenance": "source_supported",
            },
        ],
        "origin": "fixture_data",
    }
    validated = validate_playlist_synthesis_payload(
        payload,
        included_video_ids={"vid-a"},
        allowed_segment_ids={"seg-1"},
    )
    assert validated.topic_modules[0]["video_ids"] == ["vid-a"]
    assert validated.topic_modules[0]["evidence_segment_ids"] == ["seg-1"]
    assert len(validated.learning_map) == 1
    assert len(validated.key_takeaways) == 1
    assert validated.key_takeaways[0]["text"] == "Supported"
    assert "vid-excluded" in validated.dropped_video_ids
    assert "seg-x" in validated.dropped_segment_ids
