"""The single joined session lookup keeps every access check."""

from __future__ import annotations

import uuid

import anyio
from app.core.security import issue_access_token
from app.core.settings import Settings
from app.db.models import Session, User
from app.services.auth import AuthService
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": "Learner"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _ids(client: TestClient, email: str) -> tuple[str, str, str]:
    body = _register(client, email)
    factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def run() -> str:
        async with factory() as db:
            owner = uuid.UUID(body["user"]["id"])
            result = await db.execute(select(Session).where(Session.user_id == owner))
            row = result.scalars().first()
            assert row is not None
            return str(row.id)

    return body["user"]["id"], body["workspace"]["id"], anyio.run(run)


def _resolve(client: TestClient, settings: Settings, token: str) -> object | None:
    factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def run() -> object | None:
        async with factory() as db:
            return await AuthService(db, settings).resolve_access(token)

    return anyio.run(run)


def _token(settings: Settings, user: str, session: str, workspace: str) -> str:
    return issue_access_token(settings, user_id=user, session_id=session, workspace_id=workspace)


def test_valid_token_resolves_user_and_workspace(client: TestClient, settings: Settings) -> None:
    user, workspace, session = _ids(client, "lookup-ok@example.com")
    ctx = _resolve(client, settings, _token(settings, user, session, workspace))
    assert ctx is not None
    assert str(ctx.user.id) == user  # type: ignore[attr-defined]
    assert str(ctx.workspace.id) == workspace  # type: ignore[attr-defined]


def test_token_naming_another_workspace_is_rejected(client: TestClient, settings: Settings) -> None:
    user, _workspace, session = _ids(client, "lookup-a@example.com")
    _other_user, other_workspace, _other_session = _ids(client, "lookup-b@example.com")
    assert _resolve(client, settings, _token(settings, user, session, other_workspace)) is None


def test_inactive_user_and_revoked_session_are_rejected(
    client: TestClient, settings: Settings
) -> None:
    user, workspace, session = _ids(client, "lookup-off@example.com")
    token = _token(settings, user, session, workspace)
    factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def set_status(status: str) -> None:
        async with factory() as db:
            await db.execute(update(User).where(User.id == uuid.UUID(user)).values(status=status))
            await db.commit()

    anyio.run(set_status, "disabled")
    assert _resolve(client, settings, token) is None
    anyio.run(set_status, "active")
    assert _resolve(client, settings, token) is not None

    async def revoke() -> None:
        async with factory() as db:
            await db.execute(
                update(Session)
                .where(Session.id == uuid.UUID(session))
                .values(revoked_at=Session.created_at)
            )
            await db.commit()

    anyio.run(revoke)
    assert _resolve(client, settings, token) is None
