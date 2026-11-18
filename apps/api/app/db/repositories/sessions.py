"""Auth session persistence — refresh tokens stored hashed only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Session


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        refresh_token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
        device_info: dict[str, Any] | None = None,
        user_agent: str | None = None,
        rotated_from_id: uuid.UUID | None = None,
    ) -> Session:
        row = Session(
            user_id=user_id,
            workspace_id=workspace_id,
            refresh_token_hash=refresh_token_hash,
            csrf_token_hash=csrf_token_hash,
            expires_at=expires_at,
            device_info=device_info,
            user_agent=user_agent,
            rotated_from_id=rotated_from_id,
            last_seen_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        return await self._session.get(Session, session_id)

    async def get_by_refresh_hash(self, refresh_token_hash: str) -> Session | None:
        result = await self._session.execute(
            select(Session).where(Session.refresh_token_hash == refresh_token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, row: Session) -> None:
        row.revoked_at = datetime.now(UTC)
        await self._session.flush()

    async def touch(self, row: Session) -> None:
        row.last_seen_at = datetime.now(UTC)
        await self._session.flush()
