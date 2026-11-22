"""LLM-as-judge: rubric scores stay off the lesson screen unless a judge ran."""

from __future__ import annotations

import uuid

import pytest
from app.ai.contracts import ModelCapabilities, ModelRequest, ModelResult, ModelUsage
from app.retrieval.session_lanes import ORIGIN_EXTERNAL, ORIGIN_VIDEO, LanePassage
from app.services.session_judge import (
    JUDGE_INSTRUCTIONS,
    JudgeScore,
    JudgeUnavailable,
    ModelSessionJudge,
    build_judge_request,
    render_judge_input,
    select_judge,
)
from app.services.session_review import ReviewRequest
from fastapi.testclient import TestClient

from auth_helpers import auth_csrf_headers

PAPER = "A journal note about distant quasars and radio surveys."
VIDEO = "Photosynthesis converts sunlight into glucose in leaves."


def test_select_judge_skips_the_fake_provider() -> None:
    fake = _CapturingModel("fake", "fake-chat-v1", {})
    live = _CapturingModel("openai", "gpt-test", {})
    retired = _CapturingModel("gemini", "gemini-2.5-flash", {})
    explicit = _ScriptedJudge(JudgeScore(1.0, 1.0, 1.0, False))
    assert select_judge(None, fake) is None
    assert select_judge(None, None) is None
    assert select_judge(None, retired) is None
    assert isinstance(select_judge(None, live), ModelSessionJudge)
    assert select_judge(explicit, fake) is explicit


@pytest.mark.asyncio
async def test_model_judge_sees_the_draft_and_not_the_tutor_prompt() -> None:
    video = _passage(ORIGIN_VIDEO, VIDEO)
    paper = _passage(ORIGIN_EXTERNAL, PAPER, source_url="https://doi.org/10.1000/quasar-note")
    request = build_judge_request(
        question="How do leaves make glucose?",
        decision="lesson_only",
        external_search=False,
        draft=_lesson(VIDEO),
        passages=[video, paper],
        timings={str(video.id): (0, 4_000)},
    )
    model = _CapturingModel(
        "openai",
        "gpt-test",
        {
            "relevance": 0.25,
            "faithfulness": 0.5,
            "source_precision": 1,
            "fabricated_timestamp": False,
        },
    )
    score = await ModelSessionJudge(model).score(request)
    sent = model.requests[0]
    assert sent.purpose == "session_judge"
    assert sent.evidence == []
    assert sent.instructions == JUDGE_INSTRUCTIONS
    assert "no tools" in sent.instructions
    assert "flashcards" not in sent.instructions.lower()
    assert "You are LearnLens" not in sent.instructions
    assert "You are LearnLens" not in sent.user_input
    assert "QUESTION: How do leaves make glucose?" in sent.user_input
    assert "DECISION: lesson_only" in sent.user_input
    assert "CHECKBOX external_search: off" in sent.user_input
    assert f"BLOCK video_transcript id={video.id}" in sent.user_input
    assert PAPER not in sent.user_input
    assert score.relevance == 0.25
    assert score.faithfulness == 0.5
    assert score.source_precision == 1.0
    assert score.fabricated_timestamp is False


@pytest.mark.asyncio
async def test_model_judge_keeps_a_timestamp_the_video_does_not_store() -> None:
    video = _passage(ORIGIN_VIDEO, VIDEO)
    request = build_judge_request(
        question="How do leaves make glucose?",
        decision="lesson_only",
        external_search=False,
        draft=_lesson("Photosynthesis converts sunlight into glucose in leaves at 12:45."),
        passages=[video],
        timings={str(video.id): (0, 4_000)},
    )
    model = _CapturingModel(
        "openai",
        "gpt-test",
        {
            "relevance": 1,
            "faithfulness": 1,
            "source_precision": 1,
            "fabricated_timestamp": False,
        },
    )
    score = await ModelSessionJudge(model).score(request)
    assert score.fabricated_timestamp is True
    assert "12:45" in render_judge_input(request)


@pytest.mark.asyncio
async def test_retired_judge_model_is_not_called() -> None:
    model = _CapturingModel("gemini", "gemini-2.5-flash", {})
    request = build_judge_request(
        question="How do leaves make glucose?",
        decision="lesson_only",
        external_search=False,
        draft=_lesson(VIDEO),
        passages=[_passage(ORIGIN_VIDEO, VIDEO)],
    )
    with pytest.raises(JudgeUnavailable):
        await ModelSessionJudge(model).score(request)
    assert model.requests == []


def test_fake_provider_does_not_store_a_score(client: TestClient) -> None:
    _register(client, "judge-fake@example.com")
    saved = _save(client, f"{VIDEO}\n\nThe Roman senate debated grain subsidies.")
    created = _post(
        client,
        saved["video"]["id"],
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson(VIDEO),
    )
    stored = created["assistant_message"]["content_json"]
    assert stored["review_status"] == "accepted"
    assert "judge" not in stored
    assert stored["lesson"][0]["body"] == VIDEO


def test_a_running_judge_stores_scores_without_changing_the_draft(client: TestClient) -> None:
    judge = _ScriptedJudge(JudgeScore(0.64, 1.0, 1.0, False))
    client.app.state.session_judge = judge
    _register(client, "judge-store@example.com")
    saved = _save(client, f"{VIDEO}\n\nThe Roman senate debated grain subsidies.")
    created = _post(
        client,
        saved["video"]["id"],
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson(VIDEO),
    )
    stored = created["assistant_message"]["content_json"]
    assert stored["lesson"][0]["body"] == VIDEO
    assert stored["review_status"] == "accepted"
    assert stored["judge"] == {
        "relevance": 0.64,
        "faithfulness": 1.0,
        "source_precision": 1.0,
        "fabricated_timestamp": False,
    }
    assert "0.64" not in created["assistant_message"]["content"]
    assert "faithfulness" not in created["assistant_message"]["content"]
    assert judge.requests[0].question == "How does photosynthesis make glucose?"
    assert judge.requests[0].external_search is False
    assert all(row.evidence_origin == ORIGIN_VIDEO for row in judge.requests[0].passages)


def test_a_judge_error_leaves_the_draft_unchanged(client: TestClient) -> None:
    client.app.state.session_judge = _ScriptedJudge(RuntimeError("judge down"))
    _register(client, "judge-down@example.com")
    saved = _save(client, f"{VIDEO}\n\nThe Roman senate debated grain subsidies.")
    created = _post(
        client,
        saved["video"]["id"],
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson(VIDEO),
    )
    stored = created["assistant_message"]["content_json"]
    assert stored["review_status"] == "accepted"
    assert stored["lesson"][0]["body"] == VIDEO
    assert "judge" not in stored


class _ScriptedJudge:
    def __init__(self, score: JudgeScore | Exception) -> None:
        self._score = score
        self.requests: list[ReviewRequest] = []

    async def score(self, request: ReviewRequest) -> JudgeScore:
        self.requests.append(request)
        if isinstance(self._score, Exception):
            raise self._score
        return self._score


class _CapturingModel:
    capabilities = ModelCapabilities(
        supports_json_schema=True,
        supports_stream=False,
        supports_vision=False,
        supports_batch=False,
        max_context_tokens=8000,
    )

    def __init__(self, provider: str, model: str, parsed: dict) -> None:
        self.provider = provider
        self.model = model
        self._parsed = parsed
        self.requests: list[ModelRequest] = []

    async def generate_structured(self, request: ModelRequest) -> ModelResult:
        self.requests.append(request)
        return ModelResult(
            parsed=self._parsed,
            usage=ModelUsage(
                input_tokens=1,
                output_tokens=1,
                provider=self.provider,
                model=self.model,
                request_id="judge-test",
                tokens_estimated=True,
            ),
            raw_text=None,
        )

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}


def _passage(origin: str, text: str, *, source_url: str = "") -> LanePassage:
    return LanePassage(
        id=uuid.uuid4(),
        evidence_origin=origin,
        evidence_provider="gemini_youtube" if origin == ORIGIN_VIDEO else "semantic_scholar",
        text=text,
        source_url=source_url,
    )


def _lesson(body: str) -> dict:
    return {
        "lesson": [{"heading": "Answer", "body": body}],
        "external": [],
        "sources": [],
    }


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Learner"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _save(client: TestClient, transcript: str) -> dict:
    video_id = uuid.uuid4().hex[:11]
    response = client.post(
        "/api/v1/learning-history",
        headers=auth_csrf_headers(client),
        json={
            "youtube_video_id": video_id,
            "title": "Lesson",
            "channel_title": "Known channel",
            "summary": "Summary",
            "key_points": ["Point"],
            "transcript": transcript,
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _post(
    client: TestClient,
    video_id: str,
    question: str,
    *,
    external_search: bool,
    answer: dict,
) -> dict:
    response = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/messages",
        headers=auth_csrf_headers(client),
        json={
            "question": question,
            "explanation_mode": "standard",
            "external_search": external_search,
            "answer": answer,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()
