"""The messages step reuses the evidence retrieve chose for the same turn."""

from __future__ import annotations

import uuid

from app.retrieval.session_lanes import LanePassage
from app.services.packet_cache import (
    TTL_SECONDS,
    clear_packets,
    packet_key,
    remember_packet,
    take_packet,
)
from fastapi.testclient import TestClient

from auth_helpers import auth_csrf_headers

LESSON = (
    "Photosynthesis converts sunlight into glucose in leaves.\n\n"
    "Chlorophyll absorbs red and blue light."
)


def _key(**changes: object):
    base = {
        "workspace_id": uuid.UUID(int=1),
        "video_id": uuid.UUID(int=2),
        "thread_id": uuid.UUID(int=3),
        "question": "How do leaves make glucose?",
        "external_search": False,
    }
    base.update(changes)
    return packet_key(**base)  # type: ignore[arg-type]


def test_a_packet_is_used_once_and_only_for_the_same_turn() -> None:
    clear_packets()
    remember_packet(_key(), "packet", now=0.0)
    assert take_packet(_key(workspace_id=uuid.UUID(int=9)), now=1.0) is None
    assert take_packet(_key(external_search=True), now=1.0) is None
    assert take_packet(_key(question="  How do leaves   make glucose? "), now=1.0) == "packet"
    assert take_packet(_key(), now=2.0) is None


def test_an_old_packet_is_not_used() -> None:
    clear_packets()
    remember_packet(_key(), "packet", now=0.0)
    assert take_packet(_key(), now=TTL_SECONDS + 1) is None


class CountingReranker:
    def __init__(self) -> None:
        self.calls = 0

    async def rerank(
        self, *, question: str, passages: list[LanePassage]
    ) -> list[tuple[uuid.UUID, float]]:
        del question
        self.calls += 1
        return [
            (passage.id, 0.9 if "glucose" in passage.text.lower() else 0.0)
            for passage in passages
        ]


def _setup(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Learner"},
    )
    assert response.status_code == 201, response.text
    video_id = uuid.uuid4().hex[:11]
    saved = client.post(
        "/api/v1/learning-history",
        headers=auth_csrf_headers(client),
        json={
            "youtube_video_id": video_id,
            "title": "Leaves",
            "channel_title": None,
            "summary": "How leaves make food.",
            "key_points": [],
            "transcript": LESSON,
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
        },
    )
    assert saved.status_code == 200, saved.text
    return saved.json()["video"]["id"]


def _call(client: TestClient, video_id: str, step: str, body: dict) -> dict:
    response = client.post(
        f"/api/v1/lesson-chat/videos/{video_id}/{step}",
        headers=auth_csrf_headers(client),
        json=body,
    )
    assert response.status_code == 200, response.text
    return response.json()


ANSWER = {
    "lesson": [{"heading": "What it is", "body": "Leaves turn sunlight into glucose."}],
    "external": [],
    "sources": [],
}


def test_messages_reuses_the_retrieved_evidence(client: TestClient) -> None:
    clear_packets()
    reranker = CountingReranker()
    client.app.state.session_reranker = reranker
    video_id = _setup(client, "packet-reuse@example.com")
    question = "How do leaves make glucose?"
    retrieved = _call(
        client,
        video_id,
        "retrieve",
        {"question": question, "external_search": False, "sources": []},
    )
    assert reranker.calls == 1
    posted = _call(
        client,
        video_id,
        "messages",
        {
            "question": question,
            "explanation_mode": "standard",
            "external_search": False,
            "answer": ANSWER,
        },
    )
    assert reranker.calls == 1
    kept = posted["assistant_message"]["content_json"]["kept"]
    assert [row["id"] for row in kept] == [row["id"] for row in retrieved["kept"]]


def test_messages_without_retrieve_still_builds_evidence(client: TestClient) -> None:
    clear_packets()
    reranker = CountingReranker()
    client.app.state.session_reranker = reranker
    video_id = _setup(client, "packet-rebuild@example.com")
    posted = _call(
        client,
        video_id,
        "messages",
        {
            "question": "How do leaves make glucose?",
            "explanation_mode": "standard",
            "external_search": False,
            "answer": ANSWER,
        },
    )
    assert reranker.calls == 1
    assert posted["assistant_message"]["content_json"]["video_covered"] is True
