"""Two-tenant IDOR tests — workspace authorization fail-closed."""

from __future__ import annotations

import uuid

import anyio
from app.core.settings import Settings
from app.db.seed import seed_fixture_video
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse", "name": email.split("@")[0]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cross_tenant_video_access_denied(client: TestClient, settings: Settings) -> None:
    tenant_a = _register(client, "tenant-a@example.com")
    workspace_a = uuid.UUID(tenant_a["workspace"]["id"])

    # Seed fixture video into tenant A using the app engine.
    engine = client.app.state.engine
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _seed() -> uuid.UUID:
        async with session_factory() as session:
            video_id = await seed_fixture_video(
                session,
                settings,
                workspace_id=workspace_a,
                youtube_video_id="fixtureAAA001",
                title="Tenant A fixture video (synthetic)",
            )
            await session.commit()
            return video_id

    video_a_id = anyio.run(_seed)

    # Tenant A can read own video.
    own = client.get(f"/api/v1/videos/{video_a_id}")
    assert own.status_code == 200, own.text
    assert own.json()["id"] == str(video_a_id)
    assert own.json()["workspace_id"] == str(workspace_a)

    # Switch to tenant B (new cookies).
    client.cookies.clear()
    tenant_b = _register(client, "tenant-b@example.com")
    assert tenant_b["workspace"]["id"] != str(workspace_a)

    # IDOR: B requests A's video id — must not leak (404, not 200).
    idor = client.get(f"/api/v1/videos/{video_a_id}")
    assert idor.status_code == 404
    assert "fixture" not in idor.text.lower()
    assert str(video_a_id) not in idor.text or idor.json()["error"]["code"] == "NOT_FOUND"

    # Anonymous also denied.
    client.cookies.clear()
    anon = client.get(f"/api/v1/videos/{video_a_id}")
    assert anon.status_code == 401

    # Silence unused
    assert engine is not None
