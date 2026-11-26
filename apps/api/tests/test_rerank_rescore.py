"""A low video score is checked once more before the video is called "not covered"."""

from __future__ import annotations

import uuid
from typing import Any

import anyio
from app.ai.contracts import ModelRequest, ModelResult, ModelUsage
from app.retrieval.session_lanes import (
    ORIGIN_EXTERNAL,
    ORIGIN_VIDEO,
    RERANK_INSTRUCTIONS,
    LanePassage,
    rank_lane,
)
from app.retrieval.thresholds import VIDEO_COVERAGE_THRESHOLD

QUESTION = "What does data residency mean?"
PASSAGES = [
    LanePassage(
        id=uuid.UUID(int=index + 1),
        evidence_origin=ORIGIN_VIDEO,
        evidence_provider="gemini_youtube",
        text=text,
    )
    for index, text in enumerate(
        [
            "Data residency means the data stays in a chosen country or region.",
            "Teams adopted AI one after another.",
        ]
    )
]
LOW = VIDEO_COVERAGE_THRESHOLD / 2


class ScriptedModel:
    """Returns one scripted score list per call; an exception entry is raised."""

    def __init__(self, *runs: Any) -> None:
        self.runs = list(runs)
        self.requests: list[ModelRequest] = []

    async def generate_structured(self, request: ModelRequest) -> ModelResult:
        self.requests.append(request)
        run = self.runs.pop(0)
        if isinstance(run, Exception):
            raise run
        ranked = [{"id": str(PASSAGES[i].id), "score": score} for i, score in enumerate(run)]
        return ModelResult(
            parsed={"ranked": ranked},
            usage=ModelUsage(
                input_tokens=1, output_tokens=1, provider="fake", model="fake", request_id=None
            ),
        )


def _rank(model: ScriptedModel, origin: str = ORIGIN_VIDEO) -> list[LanePassage]:
    async def run() -> list[LanePassage]:
        passages = [
            LanePassage(p.id, origin, p.evidence_provider, p.text) for p in PASSAGES
        ]
        _scored, kept = await rank_lane(
            question=QUESTION, passages=passages, origin=origin, text_model=model  # type: ignore[arg-type]
        )
        return kept

    return anyio.run(run)


def test_prompt_uses_a_fixed_scale_and_asks_for_every_passage() -> None:
    for anchor in ("1.0 = ", "0.7 = ", "0.5 = ", "0.1 = ", "0.0 = "):
        assert anchor in RERANK_INSTRUCTIONS
    assert "every passage listed" in RERANK_INSTRUCTIONS
    assert "Do not skip passages" in RERANK_INSTRUCTIONS


def test_a_covering_first_score_is_not_checked_again() -> None:
    model = ScriptedModel([0.9, 0.0])
    kept = _rank(model)
    assert [p.id for p in kept] == [PASSAGES[0].id]
    assert len(model.requests) == 1


def test_a_low_first_score_is_checked_once_more_and_the_higher_score_counts() -> None:
    model = ScriptedModel([LOW, 0.0], [0.9, 0.1])
    kept = _rank(model)
    assert [p.id for p in kept] == [PASSAGES[0].id]
    assert len(model.requests) == 2


def test_an_unrelated_question_still_abstains_after_the_second_check() -> None:
    model = ScriptedModel([0.0, 0.1], [0.1, 0.0])
    assert _rank(model) == []
    assert len(model.requests) == 2


def test_a_failed_second_check_keeps_the_first_scores() -> None:
    model = ScriptedModel([LOW, 0.0], RuntimeError("busy"))
    assert _rank(model) == []
    assert len(model.requests) == 2


def test_outside_sources_are_not_checked_twice() -> None:
    model = ScriptedModel([LOW, 0.0])
    assert _rank(model, origin=ORIGIN_EXTERNAL) == []
    assert len(model.requests) == 1
