"""AuditPolicy — auditable security decisions without raw transcript/keys."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.policies.privacy_policy import PrivacyPolicy

logger = logging.getLogger("learnlens.audit")


@dataclass(frozen=True, slots=True)
class AuditRecord:
    action: str
    workspace_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AuditPolicy:
    """
    Record security-relevant events (upload, authz failure, provider change, deletion).

    Keeps an in-memory ring for tests; also emits structured logs (redacted metadata).
    Persistence to `audit_events` is optional via repository when a session is provided.
    """

    def __init__(self, *, max_records: int = 500) -> None:
        self._max = max_records
        self._lock = threading.Lock()
        self._records: list[AuditRecord] = []

    def record(self, event: AuditRecord) -> AuditRecord:
        safe_meta = PrivacyPolicy.redact_mapping(dict(event.metadata))
        safe = AuditRecord(
            action=event.action,
            workspace_id=event.workspace_id,
            actor_user_id=event.actor_user_id,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            request_id=event.request_id,
            metadata=safe_meta,
            created_at=event.created_at,
        )
        with self._lock:
            self._records.append(safe)
            if len(self._records) > self._max:
                self._records = self._records[-self._max :]
        logger.info(
            "audit_event",
            extra={
                "action": safe.action,
                "workspace_id": str(safe.workspace_id) if safe.workspace_id else None,
                "actor_user_id": str(safe.actor_user_id) if safe.actor_user_id else None,
                "resource_type": safe.resource_type,
                "resource_id": safe.resource_id,
                "request_id": safe.request_id,
                "metadata": safe.metadata,
            },
        )
        return safe

    def list_recent(self, *, limit: int = 50) -> list[AuditRecord]:
        with self._lock:
            return list(self._records[-limit:])

    def reset(self) -> None:
        with self._lock:
            self._records.clear()


_audit_policy = AuditPolicy()


def get_audit_policy() -> AuditPolicy:
    return _audit_policy


def configure_audit_policy(*, max_records: int = 500) -> AuditPolicy:
    global _audit_policy
    _audit_policy = AuditPolicy(max_records=max_records)
    return _audit_policy
