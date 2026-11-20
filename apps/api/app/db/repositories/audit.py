"""Persist audit events (metadata only — no raw transcript/keys)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policies.privacy_policy import PrivacyPolicy
from app.db.models.audit import AuditEvent


class AuditEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        action: str,
        workspace_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        summary: str | None = None,
    ) -> AuditEvent:
        row = AuditEvent(
            action=action,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            metadata_json=PrivacyPolicy.redact_mapping(metadata or {}),
            summary=PrivacyPolicy.redact_text(summary) if summary else None,
        )
        self._db.add(row)
        await self._db.flush()
        return row
