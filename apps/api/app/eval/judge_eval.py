"""Offline LLM-as-judge cases. The fixture judge is swappable and never calls a model.

Negative cases are expected rubric failures. The suite passes when those failures
are detected, clean cases stay faithful, and no foreign tenant passage is shown
to the judge. Relevance is reported and is not a hard gate.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.retrieval.session_lanes import (
    ABSTAIN_BODY,
    ABSTAIN_HEADING,
    ORIGIN_EXTERNAL,
    ORIGIN_VIDEO,
    LanePassage,
)
from app.services.session_judge import (
    JudgeScore,
    build_judge_request,
    render_judge_input,
    score_rubric,
)
from app.services.session_review import ReviewRequest

WORKSPACE_ID = "ws-lesson-a"
THREAD_ID = "thread-photosynthesis"
FOREIGN_WORKSPACE_ID = "ws-other-tenant"
VIDEO_TEXT = "Leaves capture sunlight with chlorophyll."
PAPER_TEXT = "The supplemental note states PAPER_ONLY_QUANTUM_YIELD is 0.83."
PAPER_URL = "https://doi.org/10.1000/yield-note"
FOREIGN_TEXT = "FOREIGN_TENANT_YIELD_SECRET"
VIDEO_ID = "11111111-1111-4111-8111-111111111111"
PAPER_ID = "22222222-2222-4222-8222-222222222222"
FOREIGN_ID = "33333333-3333-4333-8333-333333333333"

JudgeScorer = Callable[[ReviewRequest], JudgeScore]


@dataclass(frozen=True, slots=True)
class StoredPassage:
    id: str
    workspace_id: str
    thread_id: str
    evidence_origin: str
    text: str
    source_url: str = ""
    start_ms: int | None = None
    end_ms: int | None = None


@dataclass(frozen=True, slots=True)
class JudgeCase:
    id: str
    question: str
    decision: str
    external_search: bool
    draft: dict[str, Any]
    expect: str
    earlier_decision: str
    earlier_lesson_panel: str
    earlier_external_panel: str
    workspace_id: str = WORKSPACE_ID
    thread_id: str = THREAD_ID
    forbidden_workspace_ids: tuple[str, ...] = (FOREIGN_WORKSPACE_ID,)
    passages: tuple[StoredPassage, ...] = ()


def load_judge_cases() -> tuple[JudgeCase, ...]:
    """Five cases on one thread. Search-off turns must not see the stored paper hit."""
    stored = _stored_passages()
    return (
        JudgeCase(
            id="followup_lesson_panel",
            question="explain that",
            decision="lesson_only",
            external_search=False,
            draft=_draft(VIDEO_TEXT),
            expect="pass",
            earlier_decision="blend",
            earlier_lesson_panel=VIDEO_TEXT,
            earlier_external_panel=PAPER_TEXT,
            passages=stored,
        ),
        JudgeCase(
            id="abstain_search_off",
            question="What is the capital of the Roman grain debate?",
            decision="abstain",
            external_search=False,
            draft=_draft(ABSTAIN_BODY, heading=ABSTAIN_HEADING),
            expect="pass",
            earlier_decision="lesson_only",
            earlier_lesson_panel="",
            earlier_external_panel="",
            passages=stored,
        ),
        JudgeCase(
            id="blend_kept_urls",
            question="How do leaves capture sunlight?",
            decision="blend",
            external_search=True,
            draft=_draft(VIDEO_TEXT, external=PAPER_TEXT, url=PAPER_URL),
            expect="pass",
            earlier_decision="blend",
            earlier_lesson_panel=VIDEO_TEXT,
            earlier_external_panel=PAPER_TEXT,
            passages=stored,
        ),
        JudgeCase(
            id="paper_claim_after_search_off",
            question="explain that",
            decision="lesson_only",
            external_search=False,
            draft=_draft(PAPER_TEXT),
            expect="fail_faithfulness",
            earlier_decision="blend",
            earlier_lesson_panel=VIDEO_TEXT,
            earlier_external_panel=PAPER_TEXT,
            passages=stored,
        ),
        JudgeCase(
            id="invented_timestamp",
            question="How do leaves capture sunlight?",
            decision="lesson_only",
            external_search=False,
            draft=_draft(f"{VIDEO_TEXT.rstrip('.')} at 12:45."),
            expect="fail_timestamp",
            earlier_decision="lesson_only",
            earlier_lesson_panel=VIDEO_TEXT,
            earlier_external_panel="",
            passages=stored,
        ),
    )


def request_for_case(case: JudgeCase) -> ReviewRequest:
    allowed = _allowed_passages(case)
    timings = {
        passage.id: (passage.start_ms, passage.end_ms)
        for passage in case.passages
        if passage.id in {str(row.id) for row in allowed}
        and passage.start_ms is not None
        and passage.end_ms is not None
    }
    return build_judge_request(
        question=case.question,
        decision=case.decision,
        external_search=case.external_search,
        draft=case.draft,
        passages=allowed,
        timings=timings,
    )


def run_judge_eval(*, judge: JudgeScorer | None = None) -> dict[str, Any]:
    """Score the fixture cases. `judge` replaces the offline rubric for tests."""
    score_fn = judge or score_rubric
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    leaked_total = 0
    clean_timestamps = 0
    timestamp_detected = False
    paper_unfaithful = False
    for case in load_judge_cases():
        request = request_for_case(case)
        rendered = render_judge_input(request)
        score = score_fn(request)
        leaked = _leaked_tenant_count(case, request, rendered)
        leaked_total += leaked
        answer_passed = _answer_passed(case.expect, score, leaked)
        if case.expect == "pass" and score.fabricated_timestamp:
            clean_timestamps += 1
        if case.expect == "fail_timestamp":
            timestamp_detected = score.fabricated_timestamp
            if not score.fabricated_timestamp:
                failures.append("invented_timestamp_not_detected")
        if case.expect == "fail_faithfulness":
            paper_unfaithful = score.faithfulness < 1.0
            if not paper_unfaithful:
                failures.append("paper_claim_after_search_off_faithfulness")
        if case.expect == "pass" and not answer_passed:
            failures.append(f"clean_case:{case.id}")
        rows.append(
            {
                "id": case.id,
                "expect": case.expect,
                "passed": answer_passed,
                "thread_id": case.thread_id,
                "decision": case.decision,
                "external_search": case.external_search,
                "earlier_decision": case.earlier_decision,
                "relevance": score.relevance,
                "faithfulness": score.faithfulness,
                "source_precision": score.source_precision,
                "fabricated_timestamp": score.fabricated_timestamp,
                "leaked_tenant_count": leaked,
                "allowed_origins": [row.evidence_origin for row in request.passages],
                "allowed_ids": [str(row.id) for row in request.passages],
            }
        )
    if leaked_total != 0:
        failures.append(f"leaked_tenant_count={leaked_total}")
    if clean_timestamps != 0:
        failures.append(f"fabricated_timestamp={clean_timestamps}")
    hard_gates = {
        "fabricated_timestamp_on_clean_cases": {
            "value": clean_timestamps,
            "threshold": 0,
            "pass": clean_timestamps == 0,
        },
        "invented_timestamp_detected": {
            "value": timestamp_detected,
            "pass": timestamp_detected,
        },
        "paper_claim_after_search_off_unfaithful": {
            "value": paper_unfaithful,
            "pass": paper_unfaithful,
        },
        "leaked_tenant_count": {
            "value": leaked_total,
            "threshold": 0,
            "pass": leaked_total == 0,
        },
    }
    failing_cases = [row["id"] for row in rows if row["passed"] is False]
    return {
        "passed": len(failures) == 0,
        "fixture_data": True,
        "judge": "fixture" if judge is None else "swapped",
        "case_count": len(rows),
        "cases": rows,
        "failing_cases": failing_cases,
        "hard_gates": hard_gates,
        "soft_metrics": {
            "relevance": {
                "gated": False,
                "by_case": {row["id"]: row["relevance"] for row in rows},
            }
        },
        "gate_failures": failures,
        "notes": [
            "Fixture judge only. Swap the scorer in tests; do not call a paid API.",
            "invented_timestamp and paper_claim_after_search_off are expected rubric failures.",
            "relevance is recorded and is not a hard gate.",
        ],
    }


def _answer_passed(expect: str, score: JudgeScore, leaked: int) -> bool:
    if expect == "fail_timestamp":
        return not score.fabricated_timestamp
    if expect == "fail_faithfulness":
        return score.faithfulness >= 1.0
    return (
        score.faithfulness == 1.0
        and score.source_precision == 1.0
        and not score.fabricated_timestamp
        and leaked == 0
    )


def _allowed_passages(case: JudgeCase) -> list[LanePassage]:
    rows: list[LanePassage] = []
    for passage in case.passages:
        if passage.workspace_id != case.workspace_id:
            continue
        if passage.thread_id != case.thread_id:
            continue
        if passage.workspace_id in case.forbidden_workspace_ids:
            continue
        if passage.evidence_origin == ORIGIN_EXTERNAL and not (
            case.external_search and case.decision == "blend"
        ):
            continue
        if passage.evidence_origin not in {ORIGIN_VIDEO, ORIGIN_EXTERNAL}:
            continue
        provider = "transcript" if passage.evidence_origin == ORIGIN_VIDEO else "semantic_scholar"
        rows.append(
            LanePassage(
                id=uuid.UUID(passage.id),
                evidence_origin=passage.evidence_origin,
                evidence_provider=provider,
                text=passage.text,
                source_url=passage.source_url,
            )
        )
    return rows


def _leaked_tenant_count(case: JudgeCase, request: ReviewRequest, rendered: str) -> int:
    passages_block = rendered.split("DRAFT:", 1)[0]
    allowed_ids = {str(row.id) for row in request.passages}
    leaked = 0
    for passage in case.passages:
        foreign = (
            passage.workspace_id != case.workspace_id
            or passage.workspace_id in case.forbidden_workspace_ids
            or passage.thread_id != case.thread_id
        )
        if not foreign:
            continue
        if (passage.text and passage.text in passages_block) or passage.id in allowed_ids:
            leaked += 1
    return leaked


def _stored_passages() -> tuple[StoredPassage, ...]:
    return (
        StoredPassage(
            id=VIDEO_ID,
            workspace_id=WORKSPACE_ID,
            thread_id=THREAD_ID,
            evidence_origin=ORIGIN_VIDEO,
            text=VIDEO_TEXT,
            start_ms=0,
            end_ms=5_000,
        ),
        StoredPassage(
            id=PAPER_ID,
            workspace_id=WORKSPACE_ID,
            thread_id=THREAD_ID,
            evidence_origin=ORIGIN_EXTERNAL,
            text=PAPER_TEXT,
            source_url=PAPER_URL,
        ),
        StoredPassage(
            id=FOREIGN_ID,
            workspace_id=FOREIGN_WORKSPACE_ID,
            thread_id="thread-other",
            evidence_origin=ORIGIN_VIDEO,
            text=FOREIGN_TEXT,
            start_ms=0,
            end_ms=1_000,
        ),
    )


def _draft(
    body: str,
    *,
    heading: str = "Answer",
    external: str = "",
    url: str = "",
) -> dict[str, Any]:
    external_rows: list[dict[str, str]] = []
    sources: list[dict[str, str]] = []
    if external:
        external_rows.append({"heading": "Paper", "body": external})
    if url:
        sources.append(
            {
                "title": "Yield note",
                "url": url,
                "kind": "paper",
                "provider": "semantic_scholar",
            }
        )
    return {
        "v": 1,
        "lesson": [{"heading": heading, "body": body}],
        "external": external_rows,
        "sources": sources,
    }
