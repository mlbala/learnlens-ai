"""Workspace + membership persistence with server-side authorization helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Workspace, WorkspaceMembership


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_personal(self, *, owner_user_id: uuid.UUID, name: str) -> Workspace:
        workspace = Workspace(name=name, owner_user_id=owner_user_id)
        self._session.add(workspace)
        await self._session.flush()
        membership = WorkspaceMembership(
            user_id=owner_user_id,
            workspace_id=workspace.id,
            role="owner",
        )
        self._session.add(membership)
        await self._session.flush()
        return workspace

    async def get_membership(
        self,
        *,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> WorkspaceMembership | None:
        result = await self._session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def user_belongs(self, *, user_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
        membership = await self.get_membership(user_id=user_id, workspace_id=workspace_id)
        return membership is not None

    async def get_by_id(self, workspace_id: uuid.UUID) -> Workspace | None:
        return await self._session.get(Workspace, workspace_id)
