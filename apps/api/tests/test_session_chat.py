"""Session chat memory: one thread per lesson, segment stamp, last-8 packing."""

from __future__ import annotations

import uuid

import anyio
from app.ai.contracts import ModelCapabilities, ModelRequest, ModelResult, ModelUsage
from app.db.models import TranscriptSegment
from app.services.session_chat import (
    FollowupSection,
    FollowupSource,
    FollowupTurn,
    pack_followup,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Learner"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _save(client: TestClient, index: int) -> dict:
    video_id = f"c{index:010d}"
    response = client.post(
        "/api/v1/learning-history",
        headers=auth_csrf_headers(client),
        json={
            "youtube_video_id": video_id,
            "title": f"Lesson {index}",
            "channel_title": "Known channel",
            "summary": f"Summary {index}",
            "key_points": [f"Point {index}"],
            "transcript": f"Passage one for {index}.\n\nPassage two for {index}.",
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _answer(mark: int, *, provider: str = "semantic_scholar") -> dict:
    return {
        "lesson": [{"heading": "What it is", "body": f"LESSON_MARK_{mark}"}],
        "external": [{"heading": "What it is", "body": f"PAPER_MARK_{mark}"}],
        "sources": [
            {
                "title": f"Paper {mark}",
                "url": f"https://doi.org/10.1000/paper-{mark}",
                "kind": "paper",
                "provider": provider,
            }
        ],
    }


class _KeepReranker:
    def __init__(self, url: str = "") -> None:
        self.url = url

    async def rerank(self, *, question: str, passages: list) -> list[tuple[uuid.UUID, float]]:
        del question
        scored: list[tuple[uuid.UUID, float]] = []
        for passage in passages:
            if passage.evidence_origin == "external_search" and self.url:
                score = 0.95 if passage.source_url == self.url else 0.0
            else:
                score = 0.95
            scored.append((passage.id, score))
        return scored


def _retrieve(
    client: TestClient,
    video_id: str,
    question: str,
    sources: list[dict[str, str]],
) -> None:
    response = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/retrieve",
        headers=auth_csrf_headers(client),
        json={"question": question, "external_search": True, "sources": sources},
    )
    assert response.status_code == 200, response.text


def _post(
    client: TestClient,
    video_id: str,
    question: str,
    *,
    external_search: bool,
    answer: dict | None,
) -> dict:
    body: dict = {
        "question": question,
        "explanation_mode": "standard",
        "external_search": external_search,
    }
    if answer is not None:
        body["answer"] = answer
    response = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/messages",
        headers=auth_csrf_headers(client),
        json=body,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _segment_rows(
    client: TestClient, video_id: str
) -> list[tuple[str, str | None, str, str | None]]:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> list[tuple[str, str | None, str, str | None]]:
        async with session_factory() as session:
            result = await session.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.video_id == uuid.UUID(video_id))
                .order_by(TranscriptSegment.ordinal.asc())
            )
            rows = []
            for row in result.scalars().all():
                rows.append(
                    (
                        str(row.id),
                        None if row.thread_id is None else str(row.thread_id),
                        row.text,
                        row.evidence_origin,
                    )
                )
            return rows

    return anyio.run(_run)


def _segment_count(client: TestClient, video_id: str) -> int:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> int:
        async with session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(TranscriptSegment)
                .where(TranscriptSegment.video_id == uuid.UUID(video_id))
            )
            return int(result.scalar_one())

    return anyio.run(_run)


def test_pack_followup_keeps_last_eight_and_obeys_checkbox() -> None:
    turns = [
        FollowupTurn(
            question=f"Question {mark}",
            lesson=(FollowupSection("What it is", f"LESSON_MARK_{mark}"),),
            external=(FollowupSection("What it is", f"PAPER_MARK_{mark}"),),
            sources=(
                FollowupSource(
                    "openalex", f"Paper {mark}", f"https://doi.org/10.1000/paper-{mark}"
                ),
            ),
        )
        for mark in range(1, 10)
    ]
    off = pack_followup(turns, external_search=False)
    assert "LESSON_MARK_1" not in off
    assert "LESSON_MARK_2" in off
    assert "LESSON_MARK_9" in off
    assert "PAPER_MARK" not in off
    assert "doi.org" not in off
    assert "external_search" not in off
    assert "video_transcript" in off
    assert "explain that" in off

    on = pack_followup(turns, external_search=True)
    assert "LESSON_MARK_1" not in on
    assert "PAPER_MARK_9" in on
    assert "https://doi.org/10.1000/paper-9" in on
    assert "video_transcript" in on
    assert "external_search" in on
    assert "openalex" in on


def test_first_message_creates_one_thread_and_stamps_segments(client: TestClient) -> None:
    _register(client, "chat-memory@example.com")
    saved = _save(client, 1)
    video_id = saved["video"]["id"]
    client.app.state.session_reranker = _KeepReranker()
    segment_ids = [row["id"] for row in saved["segments"]]
    assert _segment_count(client, video_id) == 2
    before = _segment_rows(client, video_id)
    assert [row[1] for row in before] == [None, None]

    empty = client.get(f"/api/v1/lesson-chat/videos/{video_id}")
    assert empty.status_code == 200, empty.text
    assert empty.json()["thread"] is None
    assert empty.json()["messages"] == []
    assert empty.json()["segment_ids"] == segment_ids

    _retrieve(
        client,
        video_id,
        "What is the lesson about?",
        [
            {
                "title": "Paper 1",
                "url": "https://doi.org/10.1000/paper-1",
                "snippet": "Outside note PAPER_MARK_1 for the lesson.",
                "kind": "paper",
                "provider": "semantic_scholar",
            }
        ],
    )
    first = _post(
        client,
        video_id,
        "What is the lesson about?",
        external_search=True,
        answer=_answer(1),
    )
    thread_id = first["thread"]["id"]
    assert first["thread"]["scope_kind"] == "video"
    assert first["thread"]["scope_id"] == video_id
    assert first["segment_ids"] == segment_ids
    assert first["user_message"]["external_search_enabled"] is True
    assert first["user_message"]["content"] == "What is the lesson about?"
    stored = first["assistant_message"]["content_json"]
    assert stored["v"] == 1
    assert stored["lesson"][0]["body"] == "LESSON_MARK_1"
    assert stored["sources"][0]["provider"] == "semantic_scholar"
    assert "LESSON_MARK_1" in first["assistant_message"]["content"]
    assert first["assistant_message"]["content_json"]["external"][0]["body"] == "PAPER_MARK_1"

    second = _post(
        client,
        video_id,
        "explain that",
        external_search=False,
        answer={
            "lesson": [{"heading": "Answer", "body": "LESSON_MARK_followup"}],
            "external": [{"heading": "What it is", "body": "PAPER_MARK_should_not_store"}],
            "sources": _answer(99)["sources"],
        },
    )
    assert second["thread"]["id"] == thread_id
    assert second["user_message"]["external_search_enabled"] is False
    assert second["assistant_message"]["content_json"]["external"] == []
    assert second["assistant_message"]["content_json"]["sources"] == []
    assert "PAPER_MARK_should_not_store" not in second["assistant_message"]["content"]

    after = _segment_rows(client, video_id)
    assert [row[0] for row in after] == segment_ids
    assert [row[1] for row in after] == [thread_id, thread_id]
    assert [row[2] for row in after] == [row[2] for row in before]
    assert [row[3] for row in after] == ["video_transcript", "video_transcript"]
    assert _segment_count(client, video_id) == 2

    listed = client.get(f"/api/v1/lesson-chat/threads/{thread_id}/messages")
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert [item["content"] for item in items if item["role"] == "user"] == [
        "What is the lesson about?",
        "explain that",
    ]
    assert items[0]["external_search_enabled"] is True
    assert items[2]["external_search_enabled"] is False


def test_prepare_packs_last_eight_for_the_live_checkbox(client: TestClient) -> None:
    _register(client, "chat-pack@example.com")
    saved = _save(client, 2)
    video_id = saved["video"]["id"]
    reranker = _KeepReranker()
    client.app.state.session_reranker = reranker
    for mark in range(1, 10):
        provider = "tavily" if mark == 9 else "openalex"
        reranker.url = f"https://doi.org/10.1000/paper-{mark}"
        _retrieve(
            client,
            video_id,
            f"Question {mark}",
            [
                {
                    "title": f"Paper {mark}",
                    "url": f"https://doi.org/10.1000/paper-{mark}",
                    "snippet": f"Outside note PAPER_MARK_{mark}.",
                    "kind": "paper",
                    "provider": provider,
                }
            ],
        )
        _post(
            client,
            video_id,
            f"Question {mark}",
            external_search=True,
            answer=_answer(mark, provider="tavily" if mark == 9 else "openalex"),
        )

    off = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/prepare",
        headers=auth_csrf_headers(client),
        json={"external_search": False},
    )
    assert off.status_code == 200, off.text
    packed_off = off.json()["packed_history"]
    assert "Question 1" not in packed_off
    assert "LESSON_MARK_1" not in packed_off
    assert "Question 2" in packed_off
    assert "LESSON_MARK_2" in packed_off
    assert "LESSON_MARK_9" in packed_off
    assert "PAPER_MARK" not in packed_off
    assert "doi.org" not in packed_off
    assert "external_search" not in packed_off
    assert "video_transcript" in packed_off
    assert "explain that" in packed_off

    on = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/prepare",
        headers=auth_csrf_headers(client),
        json={"external_search": True},
    )
    assert on.status_code == 200, on.text
    packed_on = on.json()["packed_history"]
    assert "LESSON_MARK_1" not in packed_on
    assert "PAPER_MARK_1" not in packed_on
    assert "LESSON_MARK_9" in packed_on
    assert "PAPER_MARK_9" in packed_on
    assert "https://doi.org/10.1000/paper-9" in packed_on
    assert "video_transcript" in packed_on
    assert "external_search" in packed_on
    assert "tavily" in packed_on
    assert off.json()["thread_id"] == on.json()["thread_id"]
    assert off.json()["segment_ids"] == [row["id"] for row in saved["segments"]]


def test_fake_model_followup_omits_external_panel_when_checkbox_is_off(client: TestClient) -> None:
    owner = _register(client, "chat-model@example.com")
    saved = _save(client, 3)
    video_id = saved["video"]["id"]
    client.app.state.session_reranker = _KeepReranker()
    _retrieve(
        client,
        video_id,
        "What did the lesson say?",
        [
            {
                "title": "Paper 4",
                "url": "https://doi.org/10.1000/paper-4",
                "snippet": "Outside note PAPER_MARK_4.",
                "kind": "paper",
                "provider": "semantic_scholar",
            }
        ],
    )
    stored = _post(
        client,
        video_id,
        "What did the lesson say?",
        external_search=True,
        answer=_answer(4, provider="semantic_scholar"),
    )

    class RecordingModel:
        provider = "fake"
        model = "fake-chat-v1"
        capabilities = ModelCapabilities(
            supports_json_schema=True,
            supports_stream=False,
            supports_vision=False,
            supports_batch=False,
            max_context_tokens=8000,
        )

        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def generate_structured(self, request: ModelRequest) -> ModelResult:
            self.prompts.append(request.user_input)
            if request.purpose == "session_review":
                parsed: dict = {"accept": True, "reasons": []}
            else:
                parsed = {
                    "lesson": [{"heading": "Answer", "body": "Follow the lesson panel."}],
                    "external": [],
                }
            return ModelResult(
                parsed=parsed,
                usage=ModelUsage(
                    input_tokens=1,
                    output_tokens=1,
                    provider="fake",
                    model="fake-chat-v1",
                    request_id="fake-req",
                    tokens_estimated=True,
                ),
            )

        async def health(self) -> dict[str, str]:
            return {"status": "ok"}

    recorder = RecordingModel()
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory
    settings = client.app.state.settings

    async def _follow_up() -> None:
        from app.services.session_chat import SessionChatService

        async with session_factory() as session:
            service = SessionChatService(session, settings, text_model=recorder)
            result = await service.post_message(
                workspace_id=uuid.UUID(owner["workspace"]["id"]),
                user_id=uuid.UUID(owner["user"]["id"]),
                video_id=uuid.UUID(video_id),
                question="explain that passage one",
                explanation_mode="standard",
                external_search=False,
                answer=None,
            )
            await session.commit()
            assert result.thread.id == uuid.UUID(stored["thread"]["id"])
            payload = result.assistant_message.content_json or {}
            assert payload["external"] == []
            assert payload["sources"] == []
            assert payload["lesson"][0]["body"] == "Follow the lesson panel."

    anyio.run(_follow_up)
    assert recorder.prompts
    prompt = recorder.prompts[0]
    assert "explain that" in prompt
    assert "LESSON_MARK_4" in prompt
    assert "video_transcript" in prompt
    assert "PAPER_MARK_4" not in prompt
    assert "doi.org" not in prompt
    assert "external_search: off" in prompt


def test_http_fake_model_answers_without_a_paid_call(client: TestClient) -> None:
    _register(client, "chat-fake@example.com")
    saved = _save(client, 4)
    video_id = saved["video"]["id"]
    created = _post(
        client,
        video_id,
        "Give an example of passage one",
        external_search=False,
        answer=None,
    )
    body = created["assistant_message"]["content_json"]["lesson"][0]["body"]
    assert body == "Fixture lesson answer about the previous lesson panel."
    assert created["assistant_message"]["content_json"]["external"] == []
    assert created["user_message"]["external_search_enabled"] is False


def test_other_workspace_thread_is_not_readable_or_writable(client: TestClient) -> None:
    owner = _register(client, "chat-owner@example.com")
    saved = _save(client, 5)
    video_id = saved["video"]["id"]
    created = _post(
        client,
        video_id,
        "First question",
        external_search=True,
        answer=_answer(5),
    )
    thread_id = created["thread"]["id"]
    owner_segments = _segment_rows(client, video_id)
    client.post("/api/v1/auth/logout", headers=auth_csrf_headers(client))

    _register(client, "chat-other@example.com")
    assert client.get(f"/api/v1/lesson-chat/videos/{video_id}").status_code == 404
    assert client.get(f"/api/v1/lesson-chat/threads/{thread_id}/messages").status_code == 404
    denied = client.post(
        f"/api/v1/lesson-chat/threads/{thread_id}/messages",
        headers=auth_csrf_headers(client),
        json={
            "question": "steal the thread",
            "external_search": True,
            "explanation_mode": "standard",
        },
    )
    assert denied.status_code == 404
    denied_prepare = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/prepare",
        headers=auth_csrf_headers(client),
        json={"external_search": True},
    )
    assert denied_prepare.status_code == 404

    copied = _save(client, 5)
    assert copied["video"]["id"] != video_id
    assert [row["id"] for row in copied["segments"]] != [row["id"] for row in saved["segments"]]
    other = _post(
        client,
        copied["video"]["id"],
        "My own question",
        external_search=False,
        answer={
            "lesson": [{"heading": "Answer", "body": "Workspace B lesson."}],
            "external": [],
            "sources": [],
        },
    )
    assert other["thread"]["id"] != thread_id
    assert other["thread"]["workspace_id"] != owner["workspace"]["id"]

    still = _segment_rows(client, video_id)
    assert still == owner_segments
    assert [row[1] for row in still] == [thread_id, thread_id]
    copied_rows = _segment_rows(client, copied["video"]["id"])
    assert [row[1] for row in copied_rows] == [other["thread"]["id"], other["thread"]["id"]]
    assert [row[0] for row in copied_rows] == [row["id"] for row in copied["segments"]]
