"""Reviewer agent: origin mix, invented URLs, invented timestamps, one rewrite."""

from __future__ import annotations

import uuid

import anyio
import pytest
from app.ai.contracts import ModelCapabilities, ModelRequest, ModelResult
from app.retrieval.session_lanes import ORIGIN_EXTERNAL, ORIGIN_VIDEO, LanePassage
from app.services.session_review import (
    REVIEW_INSTRUCTIONS,
    ModelSessionReviewer,
    ReviewRequest,
    ReviewUnavailable,
    ReviewVerdict,
    build_review_request,
    deterministic_reasons,
    is_retired_chat_model,
    render_review_input,
    withheld_answer,
)
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers

PAPER = "A journal note about distant quasars and radio surveys."
PAPER_URL = "https://doi.org/10.1000/quasar-note"
GLUCOSE = (
    "Photosynthesis converts sunlight into glucose in leaves.\n\n"
    "The Roman senate debated grain subsidies."
)


def test_retired_gemini_ids_are_skipped() -> None:
    assert is_retired_chat_model("gemini-2.5-flash")
    assert is_retired_chat_model("models/gemini-2.0-flash")
    assert is_retired_chat_model("gemini-1.5-pro")
    assert not is_retired_chat_model("gemini-3.5-flash-lite")
    assert not is_retired_chat_model("fake-chat-v1")


def test_reviewer_payload_drops_external_origin_when_checkbox_is_off() -> None:
    video = _passage(ORIGIN_VIDEO, "Leaves make glucose from sunlight.")
    dropped = _passage(ORIGIN_VIDEO, "The Roman senate debated grain subsidies.")
    paper = _passage(ORIGIN_EXTERNAL, PAPER, source_url=PAPER_URL)
    request = build_review_request(
        question="How do leaves make glucose?",
        decision="lesson_only",
        external_search=False,
        draft=_lesson("Leaves make glucose from sunlight."),
        passages=[video],
        timings={},
    )
    rendered = render_review_input(request)
    assert "no tools" in REVIEW_INSTRUCTIONS
    assert "must not search the web" in REVIEW_INSTRUCTIONS
    assert video.text in rendered
    assert dropped.text not in rendered
    assert PAPER not in rendered
    assert all(row.evidence_origin == ORIGIN_VIDEO for row in request.passages)
    mixed = build_review_request(
        question="How do leaves make glucose?",
        decision="lesson_only",
        external_search=False,
        draft=_lesson("Leaves make glucose from sunlight."),
        passages=[video, paper],
        timings={},
    )
    assert PAPER not in render_review_input(mixed)
    assert all(row.evidence_origin == ORIGIN_VIDEO for row in mixed.passages)


def test_paper_used_as_the_video_is_origin_mix() -> None:
    request = _blend_request(_lesson(PAPER))
    assert "origin_mix" in deterministic_reasons(request)


def test_external_panel_when_search_is_off_is_origin_mix() -> None:
    draft = _lesson("Leaves make glucose.")
    draft["external"] = [{"heading": "What it is", "body": PAPER}]
    request = build_review_request(
        question="How do leaves make glucose?",
        decision="lesson_only",
        external_search=False,
        draft=draft,
        passages=[_passage(ORIGIN_VIDEO, "Leaves make glucose from sunlight.")],
    )
    assert "origin_mix" in deterministic_reasons(request)


def test_invented_url_is_rejected_and_a_kept_url_is_not() -> None:
    invented = _blend_request(_lesson("Leaves make glucose.", url="https://evil.example/paper"))
    assert "invented_source" in deterministic_reasons(invented)
    kept = _blend_request(_lesson("Leaves make glucose.", url=PAPER_URL))
    assert "invented_source" not in deterministic_reasons(kept)


def test_invented_timestamp_is_rejected_unless_the_video_row_stores_it() -> None:
    untimed = _blend_request(_lesson("The speaker says this at 3:01."))
    assert "invented_timestamp" in deterministic_reasons(untimed)
    video = _passage(ORIGIN_VIDEO, "Leaves make glucose from sunlight.")
    timed = build_review_request(
        question="How do leaves make glucose?",
        decision="lesson_only",
        external_search=False,
        draft=_lesson("The speaker says this at 3:01."),
        passages=[video],
        timings={str(video.id): (181_000, 190_000)},
    )
    assert "invented_timestamp" not in deterministic_reasons(timed)
    later = build_review_request(
        question="How do leaves make glucose?",
        decision="lesson_only",
        external_search=False,
        draft=_lesson("The speaker says this at 3:02."),
        passages=[video],
        timings={str(video.id): (181_000, 190_000)},
    )
    assert "invented_timestamp" in deterministic_reasons(later)


@pytest.mark.asyncio
async def test_retired_model_is_not_called() -> None:
    model = _StubModel("gemini-2.5-flash")
    reviewer = ModelSessionReviewer(model)
    with pytest.raises(ReviewUnavailable):
        await reviewer.review(_blend_request(_lesson("Leaves make glucose.")))
    assert model.calls == 0


def test_withheld_answer_is_the_ui_abstain() -> None:
    body = withheld_answer()
    assert body["lesson"] == [{"heading": "Not answered", "body": "Not answered."}]
    assert body["external"] == []
    assert body["sources"] == []
    assert "reasons" not in body


def test_accept_leaves_the_draft_unchanged(client: TestClient) -> None:
    reviewer = _ScriptedReviewer([ReviewVerdict(True, ())])
    client.app.state.session_reviewer = reviewer
    _register(client, "review-accept@example.com")
    saved = _save(client, GLUCOSE)
    created = _post(
        client,
        saved["video"]["id"],
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson("Photosynthesis converts sunlight into glucose in leaves."),
    )
    stored = created["assistant_message"]["content_json"]
    assert stored["review_status"] == "accepted"
    assert stored["lesson"] == [
        {
            "heading": "Answer",
            "body": "Photosynthesis converts sunlight into glucose in leaves.",
        }
    ]
    assert stored["external"] == []
    assert stored["sources"] == []
    assert "reasons" not in stored
    assert "origin_mix" not in str(stored)
    assert len(reviewer.requests) == 1
    assert all(row.evidence_origin == ORIGIN_VIDEO for row in reviewer.requests[0].passages)


def test_origin_mix_regenerates_once(client: TestClient) -> None:
    reviewer = _ScriptedReviewer([ReviewVerdict(False, ("origin_mix",)), ReviewVerdict(True, ())])
    client.app.state.session_reviewer = reviewer
    _register(client, "review-regen@example.com")
    saved = _save(client, GLUCOSE)
    created = _post(
        client,
        saved["video"]["id"],
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson("Photosynthesis converts sunlight into glucose in leaves."),
    )
    stored = created["assistant_message"]["content_json"]
    assert stored["review_status"] == "regenerated"
    assert stored["lesson"][0]["body"] == "Fixture lesson answer about the previous lesson panel."
    assert stored["external"] == []
    assert "origin_mix" not in str(stored)
    assert len(reviewer.requests) == 2
    assert reviewer.requests[0].passages == reviewer.requests[1].passages
    assert reviewer.requests[1].draft["lesson"][0]["body"] != (
        "Photosynthesis converts sunlight into glucose in leaves."
    )


def test_second_rejection_withholds_the_draft(client: TestClient) -> None:
    reviewer = _ScriptedReviewer(
        [
            ReviewVerdict(False, ("origin_mix",)),
            ReviewVerdict(False, ("origin_mix",)),
        ]
    )
    client.app.state.session_reviewer = reviewer
    _register(client, "review-withhold@example.com")
    saved = _save(client, GLUCOSE)
    draft = "Photosynthesis converts sunlight into glucose in leaves."
    created = _post(
        client,
        saved["video"]["id"],
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson(draft),
    )
    stored = created["assistant_message"]["content_json"]
    assert stored["review_status"] == "withheld"
    assert stored["lesson"] == [{"heading": "Not answered", "body": "Not answered."}]
    assert stored["external"] == []
    assert stored["sources"] == []
    assert draft not in created["assistant_message"]["content"]
    assert "reasons" not in stored
    assert len(reviewer.requests) == 2


def test_reviewer_timeout_withholds_without_showing_the_draft(client: TestClient) -> None:
    reviewer = _ScriptedReviewer([TimeoutError("reviewer timed out")])
    client.app.state.session_reviewer = reviewer
    _register(client, "review-timeout@example.com")
    saved = _save(client, GLUCOSE)
    draft = "UNREVIEWED_DRAFT_MARK"
    created = _post(
        client,
        saved["video"]["id"],
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson(draft),
    )
    stored = created["assistant_message"]["content_json"]
    assert stored["review_status"] == "withheld"
    assert stored["lesson"][0]["heading"] == "Not answered"
    assert draft not in created["assistant_message"]["content"]
    assert len(reviewer.requests) == 1


def test_paper_in_the_lesson_is_regenerated_or_withheld(client: TestClient) -> None:
    reviewer = _ScriptedReviewer([ReviewVerdict(True, ()), ReviewVerdict(True, ())])
    client.app.state.session_reviewer = reviewer
    client.app.state.session_reranker = _KeepReranker()
    _register(client, "review-paper@example.com")
    saved = _save(client, GLUCOSE)
    video_id = saved["video"]["id"]
    _retrieve(client, video_id, "How does photosynthesis make glucose?")
    created = _post(
        client,
        video_id,
        "How does photosynthesis make glucose?",
        external_search=True,
        answer=_lesson(PAPER, url=PAPER_URL),
    )
    stored = created["assistant_message"]["content_json"]
    assert stored["review_status"] in {"regenerated", "withheld"}
    assert PAPER not in created["assistant_message"]["content"]
    assert "reasons" not in stored


def test_invented_url_and_timestamp_are_not_stored(client: TestClient) -> None:
    reviewer = _ScriptedReviewer([ReviewVerdict(True, ()), ReviewVerdict(True, ())])
    client.app.state.session_reviewer = reviewer
    _register(client, "review-invented@example.com")
    saved = _save(client, GLUCOSE)
    created = _post(
        client,
        saved["video"]["id"],
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson(
            "The idea shows up at 3:01.",
            url="https://evil.example/not-a-source",
        ),
    )
    content = created["assistant_message"]["content"]
    stored = created["assistant_message"]["content_json"]
    assert stored["review_status"] in {"regenerated", "withheld"}
    assert "3:01" not in content
    assert "evil.example" not in content
    assert stored["external"] == []


def test_checkbox_off_hides_dropped_passages_from_the_reviewer(client: TestClient) -> None:
    reviewer = _ScriptedReviewer([ReviewVerdict(True, ())])
    client.app.state.session_reviewer = reviewer
    client.app.state.session_reranker = _DropOutsideReranker()
    _register(client, "review-payload@example.com")
    saved = _save(client, GLUCOSE)
    video_id = saved["video"]["id"]
    _retrieve(client, video_id, "How does photosynthesis make glucose?")
    created = _post(
        client,
        video_id,
        "How does photosynthesis make glucose?",
        external_search=False,
        answer=_lesson("Photosynthesis converts sunlight into glucose in leaves."),
    )
    assert created["assistant_message"]["content_json"]["review_status"] == "accepted"
    assert len(reviewer.requests) == 1
    request = reviewer.requests[0]
    rendered = render_review_input(request)
    assert request.external_search is False
    assert all(row.evidence_origin == ORIGIN_VIDEO for row in request.passages)
    assert "glucose" in rendered.lower()
    assert "senate" not in rendered.lower()
    assert PAPER not in rendered
    assert "quasar" not in rendered.lower()


def test_direct_service_timeout_does_not_regenerate(client: TestClient) -> None:
    owner = _register(client, "review-direct@example.com")
    saved = _save(client, GLUCOSE)
    model = _StubModel("fake-chat-v1")
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> dict:
        from app.services.session_chat import SessionChatService

        async with session_factory() as session:
            service = SessionChatService(
                session,
                client.app.state.settings,
                text_model=model,
                reviewer=_ScriptedReviewer([TimeoutError("reviewer timed out")]),
            )
            result = await service.post_message(
                workspace_id=uuid.UUID(owner["workspace"]["id"]),
                user_id=uuid.UUID(owner["user"]["id"]),
                video_id=uuid.UUID(saved["video"]["id"]),
                question="How does photosynthesis make glucose?",
                explanation_mode="standard",
                external_search=False,
                answer=_lesson("UNREVIEWED_DRAFT_MARK"),
            )
            await session.commit()
            return result.assistant_message.content_json or {}

    stored = anyio.run(_run)
    assert stored["review_status"] == "withheld"
    assert "UNREVIEWED_DRAFT_MARK" not in str(stored)
    assert model.calls == 0


class _ScriptedReviewer:
    def __init__(self, verdicts: list[ReviewVerdict | Exception]) -> None:
        self._verdicts = list(verdicts)
        self.requests: list[ReviewRequest] = []

    async def review(self, request: ReviewRequest) -> ReviewVerdict:
        self.requests.append(request)
        verdict = self._verdicts.pop(0)
        if isinstance(verdict, Exception):
            raise verdict
        return verdict


class _KeepReranker:
    async def rerank(
        self,
        *,
        question: str,
        passages: list[LanePassage],
    ) -> list[tuple[uuid.UUID, float]]:
        del question
        return [(passage.id, 0.95) for passage in passages]


class _DropOutsideReranker:
    async def rerank(
        self,
        *,
        question: str,
        passages: list[LanePassage],
    ) -> list[tuple[uuid.UUID, float]]:
        del question
        scored: list[tuple[uuid.UUID, float]] = []
        for passage in passages:
            if passage.evidence_origin == ORIGIN_EXTERNAL or "senate" in passage.text.lower():
                score = 0.0
            else:
                score = 0.9
            scored.append((passage.id, score))
        return scored


class _StubModel:
    provider = "fake"
    capabilities = ModelCapabilities(
        supports_json_schema=True,
        supports_stream=False,
        supports_vision=False,
        supports_batch=False,
        max_context_tokens=8000,
    )

    def __init__(self, model: str) -> None:
        self.model = model
        self.calls = 0

    async def generate_structured(self, request: ModelRequest) -> ModelResult:
        del request
        self.calls += 1
        raise AssertionError("model should not be called")

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}


def _blend_request(draft: dict) -> ReviewRequest:
    video = _passage(ORIGIN_VIDEO, "Photosynthesis converts sunlight into glucose in leaves.")
    paper = _passage(ORIGIN_EXTERNAL, PAPER, source_url=PAPER_URL)
    return build_review_request(
        question="How does photosynthesis make glucose?",
        decision="blend",
        external_search=True,
        draft=draft,
        passages=[video, paper],
    )


def _lesson(body: str, *, url: str = "") -> dict:
    sources = []
    if url:
        sources.append(
            {
                "title": "Source",
                "url": url,
                "kind": "paper",
                "provider": "semantic_scholar",
            }
        )
    return {
        "lesson": [{"heading": "Answer", "body": body}],
        "external": [],
        "sources": sources,
    }


def _passage(origin: str, text: str, *, source_url: str = "") -> LanePassage:
    return LanePassage(
        id=uuid.uuid4(),
        evidence_origin=origin,
        evidence_provider="gemini_youtube" if origin == ORIGIN_VIDEO else "semantic_scholar",
        text=text,
        source_url=source_url,
    )


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


def _retrieve(client: TestClient, video_id: str, question: str) -> None:
    response = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/retrieve",
        headers=auth_csrf_headers(client),
        json={
            "question": question,
            "external_search": True,
            "sources": [
                {
                    "title": "Quasar survey",
                    "url": PAPER_URL,
                    "snippet": PAPER,
                    "kind": "paper",
                    "provider": "semantic_scholar",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
