"""Outside lane subject gate: drop a different subject, keep related topics."""

from __future__ import annotations

import json
import uuid

import pytest
from app.ai.contracts import ModelRequest, ModelResult
from app.db.models import Video
from app.retrieval.session_lanes import ORIGIN_EXTERNAL, ORIGIN_VIDEO, LanePassage
from app.retrieval.subject_gate import (
    SUBJECT_DIFFERENT,
    SUBJECT_RELATED,
    SUBJECT_SAME,
    ModelSubjectGate,
    gate_by_subject,
    lesson_subject,
    lexical_relation,
)
from app.services.answer_usage import answer_usage_line
from app.services.session_review import ReviewVerdict
from fastapi.testclient import TestClient

from auth_helpers import auth_csrf_headers

ATTENTION_SUBJECT = (
    "Attention Is All You Need\n"
    "The paper replaces recurrent and convolutional sequence models with the Transformer, "
    "a network built only on attention. It trains in parallel and improves machine "
    "translation.\nSelf-attention\nMulti-head attention\nPositional encoding"
)
RNN_QUESTION = "What is the issue with current RNNs?"
RNN_PAPER = (
    "Recurrent neural networks process a sequence one step at a time, so training cannot "
    "run in parallel and long-range dependencies fade during translation."
)

GRID_SUBJECT = (
    "How power transformers work\n"
    "A transformer moves electrical energy between circuits through a shared magnetic core. "
    "Primary and secondary windings set the voltage ratio.\nWindings\nCore losses\nTurns ratio"
)
TRANSFORMER_QUESTION = "What is a transformer?"
ML_PAPER = (
    "The Transformer is a neural network architecture based on self-attention that "
    "replaced recurrent models for language tasks."
)
GRID_PAPER = (
    "Distribution transformers step voltage down using copper windings around a laminated "
    "magnetic core to limit eddy current losses."
)


def _external(text: str) -> LanePassage:
    return LanePassage(
        id=uuid.uuid4(),
        evidence_origin=ORIGIN_EXTERNAL,
        evidence_provider="openalex",
        text=text,
        source_url=f"https://example.org/{uuid.uuid4().hex[:8]}",
    )


# --- Lexical rule ----------------------------------------------------------------


def test_lexical_keeps_a_related_topic() -> None:
    relation = lexical_relation(subject=ATTENTION_SUBJECT, question=RNN_QUESTION, text=RNN_PAPER)
    assert relation == SUBJECT_RELATED


def test_lexical_drops_the_other_meaning_of_a_question_word() -> None:
    relation = lexical_relation(
        subject=GRID_SUBJECT, question=TRANSFORMER_QUESTION, text=ML_PAPER
    )
    # "transformer" is shared, but it came from the question, so it does not count.
    assert relation == SUBJECT_DIFFERENT
    same_field = lexical_relation(
        subject=GRID_SUBJECT, question=TRANSFORMER_QUESTION, text=GRID_PAPER
    )
    assert same_field == SUBJECT_RELATED


@pytest.mark.asyncio
async def test_thin_subject_keeps_everything() -> None:
    passages = [_external(ML_PAPER)]
    kept, dropped = await gate_by_subject(
        passages, subject="Untitled", question=TRANSFORMER_QUESTION, gate=_FixedGate({})
    )
    assert kept == passages
    assert dropped == 0


@pytest.mark.asyncio
async def test_no_gate_keeps_everything() -> None:
    passages = [_external(ML_PAPER)]
    kept, dropped = await gate_by_subject(
        passages, subject=GRID_SUBJECT, question=TRANSFORMER_QUESTION, gate=None
    )
    assert kept == passages
    assert dropped == 0


# --- Model gate -----------------------------------------------------------------


class _StubModel:
    provider = "fake"
    model = "fake-chat-v1"

    def __init__(self, payload: dict | Exception) -> None:
        self.payload = payload
        self.requests: list[ModelRequest] = []

    async def generate_structured(self, request: ModelRequest) -> ModelResult:
        self.requests.append(request)
        if isinstance(self.payload, Exception):
            raise self.payload
        return ModelResult(parsed=self.payload, usage=None, raw_text=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_model_gate_drops_only_a_different_subject() -> None:
    related, other, same = _external(RNN_PAPER), _external(ML_PAPER), _external(GRID_PAPER)
    model = _StubModel(
        {
            "verdicts": [
                {"id": str(related.id), "relation": "related"},
                {"id": str(other.id), "relation": "different"},
                {"id": str(same.id), "relation": "same"},
            ]
        }
    )
    kept, dropped = await gate_by_subject(
        [related, other, same],
        subject=GRID_SUBJECT,
        question=TRANSFORMER_QUESTION,
        gate=ModelSubjectGate(model),  # type: ignore[arg-type]
    )
    assert kept == [related, same]
    assert dropped == 1
    request = model.requests[0]
    assert request.purpose == "session_subject_gate"
    assert "SUBJECT:" in request.user_input
    assert "QUESTION:" in request.user_input
    assert "no tools" in request.instructions


@pytest.mark.asyncio
async def test_model_gate_failure_uses_the_lexical_rule() -> None:
    other = _external(ML_PAPER)
    grid = _external(GRID_PAPER)
    kept, dropped = await gate_by_subject(
        [other, grid],
        subject=GRID_SUBJECT,
        question=TRANSFORMER_QUESTION,
        gate=ModelSubjectGate(_StubModel(TimeoutError("slow"))),  # type: ignore[arg-type]
    )
    assert kept == [grid]
    assert dropped == 1


@pytest.mark.asyncio
async def test_ids_the_model_skips_or_mislabels_use_the_lexical_rule() -> None:
    judged = _external(GRID_PAPER)
    skipped = _external(ML_PAPER)
    model = _StubModel(
        {
            "verdicts": [
                {"id": str(judged.id), "relation": "same"},
                {"id": str(uuid.uuid4()), "relation": "same"},
                {"id": str(skipped.id), "relation": "maybe"},
            ]
        }
    )
    kept, dropped = await gate_by_subject(
        [judged, skipped],
        subject=GRID_SUBJECT,
        question=TRANSFORMER_QUESTION,
        gate=ModelSubjectGate(model),  # type: ignore[arg-type]
    )
    assert kept == [judged]
    assert dropped == 1


def test_lesson_subject_uses_title_summary_and_key_points() -> None:
    video = Video(
        workspace_id=uuid.uuid4(),
        youtube_video_id="abcdefghijk",
        title="How power transformers work",
        metadata_json={
            "gemini_lesson": {"summary": "Windings set the ratio.", "key_points": ["Core"]}
        },
    )
    assert lesson_subject(video) == "How power transformers work\nWindings set the ratio.\nCore"
    bare = Video(workspace_id=uuid.uuid4(), youtube_video_id="abcdefghijk", title="T")
    assert lesson_subject(bare) == "T"


def test_usage_line_counts_dropped_results() -> None:
    line = answer_usage_line(
        workspace_id=uuid.uuid4(),
        video_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        decision="lesson_only",
        review_status="accepted",
        external_search_enabled=True,
        kept_video_passages=2,
        kept_outside_passages=0,
        dropped_off_subject=3,
    )
    assert json.loads(line)["dropped_off_subject"] == 3


# --- Through the API -------------------------------------------------------------


class _FixedGate:
    def __init__(self, relation_for_all: dict | str) -> None:
        self.relation = relation_for_all
        self.subjects: list[str] = []

    async def classify(self, *, subject, question, passages):  # type: ignore[no-untyped-def]
        self.subjects.append(subject)
        if isinstance(self.relation, dict):
            return self.relation
        return {passage.id: self.relation for passage in passages}


class _KeepAll:
    async def rerank(self, *, question, passages):  # type: ignore[no-untyped-def]
        del question
        return [(passage.id, 0.95) for passage in passages]


class _Accept:
    async def review(self, request):  # type: ignore[no-untyped-def]
        del request
        return ReviewVerdict(True, ())


def _lesson_turn(client: TestClient, email: str, gate: _FixedGate) -> dict:
    client.app.state.session_reranker = _KeepAll()
    client.app.state.session_reviewer = _Accept()
    client.app.state.session_subject_gate = gate
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Learner"},
    )
    assert response.status_code == 201, response.text
    saved = client.post(
        "/api/v1/learning-history",
        headers=auth_csrf_headers(client),
        json={
            "youtube_video_id": "g0000000001",
            "title": "How power transformers work",
            "channel_title": None,
            "summary": "A transformer moves energy between circuits through a magnetic core.",
            "key_points": ["Windings", "Turns ratio", "Core losses"],
            "transcript": "Windings set the voltage ratio.\n\nThe core carries magnetic flux.",
            "source_url": "https://www.youtube.com/watch?v=g0000000001",
        },
    )
    assert saved.status_code == 200, saved.text
    video_id = saved.json()["video"]["id"]
    url = "https://arxiv.org/abs/1706.03762"
    retrieved = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/retrieve",
        headers=auth_csrf_headers(client),
        json={
            "question": TRANSFORMER_QUESTION,
            "external_search": True,
            "sources": [
                {
                    "title": "Attention Is All You Need",
                    "url": url,
                    "snippet": ML_PAPER,
                    "kind": "paper",
                    "provider": "semantic_scholar",
                }
            ],
        },
    )
    assert retrieved.status_code == 200, retrieved.text
    blend = retrieved.json().get("decision") == "blend"
    posted = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/messages",
        headers=auth_csrf_headers(client),
        json={
            "question": TRANSFORMER_QUESTION,
            "explanation_mode": "standard",
            "external_search": True,
            "answer": {
                "lesson": [{"heading": "Answer", "body": "Windings set the voltage ratio."}],
                "external": (
                    [{"heading": "Papers", "body": "A related architecture shares the name."}]
                    if blend
                    else []
                ),
                "sources": (
                    [
                        {
                            "title": "Attention Is All You Need",
                            "url": url,
                            "kind": "paper",
                            "provider": "semantic_scholar",
                        }
                    ]
                    if blend
                    else []
                ),
            },
        },
    )
    assert posted.status_code == 200, posted.text
    stored = posted.json()["assistant_message"]["content_json"]
    return {"retrieve": retrieved.json(), "stored": stored}


def test_a_different_subject_is_not_shown_and_the_turn_says_why(client: TestClient) -> None:
    gate = _FixedGate(SUBJECT_DIFFERENT)
    result = _lesson_turn(client, "gate-different@example.com", gate)
    stored = result["stored"]
    assert result["retrieve"]["decision"] != "blend"
    assert all(
        row["evidence_origin"] == ORIGIN_VIDEO for row in result["retrieve"].get("passages", [])
    )
    assert stored["external"] == []
    assert stored["sources"] == []
    assert stored["outside_off_subject"] is True
    assert "power transformers" in gate.subjects[0].lower()


@pytest.mark.parametrize("relation", [SUBJECT_RELATED, SUBJECT_SAME])
def test_a_related_or_same_subject_is_still_shown(client: TestClient, relation: str) -> None:
    result = _lesson_turn(client, f"gate-{relation}@example.com", _FixedGate(relation))
    stored = result["stored"]
    assert stored["decision"] == "blend"
    assert stored["outside_off_subject"] is False
    assert stored["sources"][0]["url"] == "https://arxiv.org/abs/1706.03762"
