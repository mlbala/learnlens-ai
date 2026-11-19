"""YouTube metadata import tests — fake fixtures only; no paid API calls."""

from __future__ import annotations

from fastapi.testclient import TestClient

from auth_helpers import auth_csrf_headers


def _register(client: TestClient, email: str = "importer@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse", "name": "Importer"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_video_import_from_fixture_sets_needs_transcript(client: TestClient) -> None:
    _register(client)
    headers = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/videos/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/watch?v=vidPublic01"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] is True
    assert body["transcript_from_url"] is False
    video = body["video"]
    assert video["youtube_video_id"] == "vidPublic01"
    assert video["status"] == "needs_transcript"
    assert video["status"] != "ready"
    assert video["transcript_access"] is False
    assert video["coverage"] == "metadata_only"
    assert any(n["code"] == "SOURCE_TRANSCRIPT_REQUIRED" for n in body["notices"])
    assert "fixture" in (video["title"] or "").lower() or video["metadata_json"].get(
        "fixture_data"
    )


def test_video_reimport_is_idempotent(client: TestClient) -> None:
    _register(client)
    headers = auth_csrf_headers(client)
    url = {"youtube_url": "https://youtu.be/vidPublic02"}
    first = client.post("/api/v1/videos/import", headers=headers, json=url)
    second = client.post("/api/v1/videos/import", headers=headers, json=url)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["video"]["id"] == second.json()["video"]["id"]
    assert second.json()["created"] is False
    assert second.json()["video"]["status"] == "needs_transcript"


def test_idempotency_key_replays_same_video(client: TestClient) -> None:
    _register(client)
    headers = {**auth_csrf_headers(client), "Idempotency-Key": "video-key-1"}
    url = {"youtube_url": "https://www.youtube.com/shorts/vidPublic03"}
    first = client.post("/api/v1/videos/import", headers=headers, json=url)
    second = client.post("/api/v1/videos/import", headers=headers, json=url)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["video"]["id"] == second.json()["video"]["id"]
    assert any(n["code"] == "IDEMPOTENT_REPLAY" for n in second.json()["notices"])


def test_import_never_marks_summarized(client: TestClient) -> None:
    _register(client)
    headers = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/videos/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/watch?v=vidPublic01"},
    )
    status = response.json()["video"]["status"]
    assert status not in {"ready", "summarizing", "indexing", "summarized"}


def test_unavailable_video_persists_unavailable(client: TestClient) -> None:
    _register(client)
    headers = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/videos/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/watch?v=vidPrivate9"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["video"]["status"] == "unavailable"


def test_malicious_url_rejected_before_any_fetch(client: TestClient) -> None:
    _register(client)
    headers = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/videos/import",
        headers=headers,
        json={"youtube_url": "https://youtube.com.evil.example/watch?v=vidPublic01"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {"INVALID_HOST", "INVALID_URL", "UNSUPPORTED_URL"}


def test_playlist_url_rejected_on_video_endpoint(client: TestClient) -> None:
    _register(client)
    headers = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/videos/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/playlist?list=PLfixtureCourse01"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "WRONG_URL_KIND"


def test_multipart_playlist_preserves_order_and_missing_items(client: TestClient) -> None:
    _register(client)
    headers = auth_csrf_headers(client)
    response = client.post(
        "/api/v1/playlists/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/playlist?list=PLfixtureCourse01"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["transcript_from_url"] is False
    playlist = body["playlist"]
    items = playlist["items"]
    assert len(items) == 7
    assert [i["playlist_position"] for i in items] == list(range(7))
    assert items[0]["youtube_video_id"] == "vidPublic01"
    assert items[0]["state"] == "needs_transcript"
    assert items[2]["youtube_video_id"] == "vidPrivate9"
    assert items[2]["state"] == "unavailable"
    assert items[4]["youtube_video_id"] == "vidDeleted1"
    assert items[4]["state"] == "unavailable"
    assert items[6]["youtube_video_id"] == "vidUnavail1"
    assert items[6]["state"] == "unavailable"
    coverage = playlist["coverage"]
    assert coverage["total"] == 7
    assert coverage["needs_transcript"] == 4
    assert coverage["unavailable"] == 3
    assert coverage["ready"] == 0

    # Re-import same playlist — idempotent identity
    again = client.post(
        "/api/v1/playlists/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/playlist?list=PLfixtureCourse01"},
    )
    assert again.status_code == 200
    assert again.json()["playlist"]["id"] == playlist["id"]
    assert again.json()["created"] is False

    # GET preserves order
    detail = client.get(f"/api/v1/playlists/{playlist['id']}")
    assert detail.status_code == 200
    got = detail.json()["items"]
    assert [i["youtube_video_id"] for i in got] == [i["youtube_video_id"] for i in items]


def test_list_videos_scoped_to_workspace(client: TestClient) -> None:
    _register(client, "lister@example.com")
    headers = auth_csrf_headers(client)
    client.post(
        "/api/v1/videos/import",
        headers=headers,
        json={"youtube_url": "https://www.youtube.com/watch?v=vidPublic01"},
    )
    listed = client.get("/api/v1/videos")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) >= 1
