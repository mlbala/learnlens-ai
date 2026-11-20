"""Phase 18 — tutor/quiz/spaced-review/concept graph (fake providers only)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import anyio
from app.ai.contracts import ModelRequest, ModelResult, ModelUsage
from app.core.settings import Settings
from app.db.seed import seed_fixture_video
from app.domain.spaced_review import advance_schedule, initial_schedule
from app.domain.tutor_validate import validate_tutor_payload
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import auth_csrf_headers

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "transcripts"


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Tutor Tester"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_video(
    client: TestClient,
    settings: Settings,
    workspace_id: uuid.UUID,
    *,
    youtube_video_id: str = "fixtureTutor01",
    title: str = "Fixture lecture for tutor (synthetic)",
) -> uuid.UUID:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> uuid.UUID:
        async with session_factory() as session:
            video_id = await seed_fixture_video(
                session,
                settings,
                workspace_id=workspace_id,
                youtube_video_id=youtube_video_id,
                title=title,
            )
            await session.commit()
            return video_id

    return anyio.run(_run)


def _upload(client: TestClient, video_id: uuid.UUID, *, idem: str) -> dict:
    headers = auth_csrf_headers(client)
    raw = (FIXTURES / "sample.srt").read_bytes()
    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers={**headers, "Idempotency-Key": idem},
        data={"rights_attested": "true", "source_kind": "srt"},
        files={"file": ("sample.srt", raw, "application/x-subrip")},
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_spaced_review_advance_good() -> None:
    base = initial_schedule()
    nxt = advance_schedule(
        interval_days=base.interval_days,
        ease_factor=base.ease_factor,
        repetitions=base.repetitions,
        grade="good",
    )
    assert nxt.repetitions == 1
    assert nxt.interval_days == 1.0
    assert nxt.last_result == "good"


def test_validate_drops_unsupported_citations() -> None:
    allowed = frozenset({"seg-real"})
    payload = {
        "title": "t",
        "origin": "fixture_data",
        "concepts": [
            {
                "name": "C",
                "description": "d",
                "evidence_segment_ids": ["seg-invented"],
                "prerequisites": [],
            }
        ],
        "items": [
            {
                "item_kind": "flashcard",
                "prompt": "p",
                "answer": "a",
                "explanation": "e",
                "explanation_origin": "source_supported",
                "choices": [],
                "correct_choice_index": None,
                "evidence_segment_ids": ["seg-invented"],
                "concept_name": "C",
                "presentation": {},
            },
            {
                "item_kind": "quiz",
                "prompt": "q",
                "answer": "ok",
                "explanation": "ai",
                "explanation_origin": "ai_generated_illustration",
                "choices": ["ok", "no"],
                "correct_choice_index": 0,
                "evidence_segment_ids": ["seg-real"],
                "concept_name": None,
                "presentation": {},
            },
        ],
    }
    validated = validate_tutor_payload(payload, allowed_segment_ids=allowed)
    assert len(validated.items) == 1
    assert validated.items[0]["evidence_segment_ids"] == ["seg-real"]
    assert "seg-invented" in validated.dropped_citation_ids
    assert validated.concepts == []


def test_generate_deck_resolves_evidence_and_labels_ai_illustration(
    client: TestClient, settings: Settings
) -> None:
    body = _register(client, "tutor-gen@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    _upload(client, video_id, idem="tutor-gen-1")
    headers = auth_csrf_headers(client)

    response = client.post(
        "/api/v1/tutor/decks",
        headers=headers,
        json={"video_id": str(video_id), "presentation_language": "en"},
    )
    assert response.status_code == 200, response.text
    deck = response.json()
    assert deck["origin"] == "fixture_data"
    assert "learning-efficacy" in deck["disclaimer"].lower() or "evaluation" in deck[
        "disclaimer"
    ].lower()
    assert len(deck["items"]) >= 2
    quiz = next(i for i in deck["items"] if i["item_kind"] == "quiz")
    assert quiz["explanation_origin"] == "ai_generated_illustration"
    assert quiz["evidence"]
    assert all(e["segment_id"] for e in quiz["evidence"])
    assert any(e.get("snippet") for e in quiz["evidence"])
    assert deck["concept_edges"]
    assert deck["concept_edges"][0]["relation"] == "prerequisite"


def test_quiz_attempt_resolves_evidence_and_progress_isolated(
    client: TestClient, settings: Settings
) -> None:
    a = _register(client, "tutor-a@example.com")
    workspace_a = uuid.UUID(a["workspace"]["id"])
    video_a = _seed_video(client, settings, workspace_a, youtube_video_id="fixtureTutorA")
    _upload(client, video_a, idem="tutor-a-up")
    headers_a = auth_csrf_headers(client)

    deck_resp = client.post(
        "/api/v1/tutor/decks",
        headers=headers_a,
        json={"video_id": str(video_a)},
    )
    assert deck_resp.status_code == 200, deck_resp.text
    deck = deck_resp.json()
    quiz = next(i for i in deck["items"] if i["item_kind"] == "quiz")

    attempt = client.post(
        f"/api/v1/tutor/decks/{deck['id']}/attempts",
        headers=headers_a,
        json={"item_id": quiz["id"], "selected_choice_index": 0},
    )
    assert attempt.status_code == 200, attempt.text
    body = attempt.json()
    assert body["is_correct"] is True
    assert body["evidence_resolved"] is True
    assert body["evidence"]
    assert body["explanation_origin"] == "ai_generated_illustration"

    progress = client.get("/api/v1/tutor/progress", headers=headers_a)
    assert progress.status_code == 200
    rows = progress.json()["items"]
    assert len(rows) == 1
    assert rows[0]["items_seen"] == 1
    assert rows[0]["items_correct"] == 1
    assert rows[0]["user_id"] == a["user"]["id"]

    # Second user cannot see first user's deck / progress
    client.post("/api/v1/auth/logout", headers=headers_a)
    b = _register(client, "tutor-b@example.com")
    headers_b = auth_csrf_headers(client)
    foreign = client.get(f"/api/v1/tutor/decks/{deck['id']}", headers=headers_b)
    assert foreign.status_code == 404
    prog_b = client.get("/api/v1/tutor/progress", headers=headers_b)
    assert prog_b.status_code == 200
    assert prog_b.json()["items"] == []
    assert b["user"]["id"] != a["user"]["id"]


def test_delete_generated_deck(client: TestClient, settings: Settings) -> None:
    body = _register(client, "tutor-del@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(
        client, settings, workspace_id, youtube_video_id="fixtureTutorDel"
    )
    _upload(client, video_id, idem="tutor-del-up")
    headers = auth_csrf_headers(client)
    deck = client.post(
        "/api/v1/tutor/decks",
        headers=headers,
        json={"video_id": str(video_id)},
    ).json()
    deleted = client.delete(f"/api/v1/tutor/decks/{deck['id']}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    missing = client.get(f"/api/v1/tutor/decks/{deck['id']}", headers=headers)
    assert missing.status_code == 404


def test_cross_tenant_video_generate_404(client: TestClient, settings: Settings) -> None:
    a = _register(client, "tutor-tenant-a@example.com")
    workspace_a = uuid.UUID(a["workspace"]["id"])
    video_a = _seed_video(
        client, settings, workspace_a, youtube_video_id="fixtureTutorTenant"
    )
    _upload(client, video_a, idem="tutor-tenant-up")
    headers_a = auth_csrf_headers(client)
    client.post("/api/v1/auth/logout", headers=headers_a)

    _register(client, "tutor-tenant-b@example.com")
    headers_b = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/tutor/decks",
        headers=headers_b,
        json={"video_id": str(video_a)},
    )
    assert response.status_code == 404


def test_unsupported_invented_citations_blocked(
    client: TestClient, settings: Settings, monkeypatch
) -> None:
    class InventingTutorAdapter:
        provider = "fake"
        model = "fake-invent-tutor"

        def __init__(self, invented: str) -> None:
            from app.ai.contracts import ModelCapabilities

            self.capabilities = ModelCapabilities(
                supports_json_schema=True,
                supports_stream=False,
                supports_vision=False,
                supports_batch=False,
                max_context_tokens=32_000,
            )
            self._invented = invented

        async def generate_structured(self, request: ModelRequest) -> ModelResult:
            return ModelResult(
                parsed={
                    "title": "bad",
                    "origin": "fixture_data",
                    "concepts": [],
                    "items": [
                        {
                            "item_kind": "flashcard",
                            "prompt": "p",
                            "answer": "a",
                            "explanation": "e",
                            "explanation_origin": "source_supported",
                            "choices": [],
                            "correct_choice_index": None,
                            "evidence_segment_ids": [self._invented],
                            "concept_name": None,
                            "presentation": {},
                        }
                    ],
                },
                usage=ModelUsage(
                    input_tokens=1,
                    output_tokens=1,
                    provider="fake",
                    model=self.model,
                    request_id="invent",
                    tokens_estimated=True,
                ),
            )

        async def health(self) -> dict[str, str]:
            return {"status": "ok"}

    body = _register(client, "tutor-invent@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(
        client, settings, workspace_id, youtube_video_id="fixtureTutorInvent"
    )
    _upload(client, video_id, idem="tutor-invent-up")

    from app.services import tutor as tutor_mod

    invented = str(uuid.uuid4())
    original = tutor_mod.build_text_model

    def _fake_build(_settings: Settings) -> Any:
        return InventingTutorAdapter(invented)

    monkeypatch.setattr(tutor_mod, "build_text_model", _fake_build)
    headers = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/tutor/decks",
        headers=headers,
        json={"video_id": str(video_id)},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "TUTOR_UNSUPPORTED_EVIDENCE"
    monkeypatch.setattr(tutor_mod, "build_text_model", original)


def test_review_and_preferences_ta(client: TestClient, settings: Settings) -> None:
    body = _register(client, "tutor-review@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(
        client, settings, workspace_id, youtube_video_id="fixtureTutorReview"
    )
    _upload(client, video_id, idem="tutor-review-up")
    headers = auth_csrf_headers(client)

    prefs = client.put(
        "/api/v1/tutor/preferences",
        headers=headers,
        json={"presentation_language": "ta"},
    )
    assert prefs.status_code == 200
    assert prefs.json()["presentation_language"] == "ta"

    deck = client.post(
        "/api/v1/tutor/decks",
        headers=headers,
        json={"video_id": str(video_id), "presentation_language": "ta"},
    ).json()
    assert deck["presentation_language"] == "ta"
    item_id = deck["items"][0]["id"]

    due = client.get("/api/v1/tutor/review", headers=headers)
    assert due.status_code == 200
    assert len(due.json()["items"]) >= 1

    reviewed = client.post(
        f"/api/v1/tutor/review/{item_id}",
        headers=headers,
        json={"grade": "good"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["repetitions"] >= 1
    assert reviewed.json()["last_result"] == "good"


def test_generate_requires_transcript(client: TestClient, settings: Settings) -> None:
    body = _register(client, "tutor-notrx@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(
        client, settings, workspace_id, youtube_video_id="fixtureTutorNoTrx"
    )
    headers = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/tutor/decks",
        headers=headers,
        json={"video_id": str(video_id)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_TRANSCRIPT_REQUIRED"
