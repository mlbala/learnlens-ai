"""Tenant / scope filters — UUID-only, never free-form client Qdrant filters."""

from __future__ import annotations

import uuid
from typing import Any

from app.retrieval.contracts import TenantScopeFilter
from app.retrieval.errors import InvalidRetrievalFilter


def parse_uuid(value: object, *, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise InvalidRetrievalFilter(
                f"{field_name} must be a UUID.",
                details={"field": field_name},
            )
        try:
            return uuid.UUID(text)
        except ValueError as exc:
            raise InvalidRetrievalFilter(
                f"{field_name} is not a valid UUID.",
                details={"field": field_name},
            ) from exc
    raise InvalidRetrievalFilter(
        f"{field_name} must be a UUID string.",
        details={"field": field_name, "got_type": type(value).__name__},
    )


def parse_uuid_list(values: object, *, field_name: str) -> tuple[uuid.UUID, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise InvalidRetrievalFilter(
            f"{field_name} must be a list of UUIDs.",
            details={"field": field_name},
        )
    out: list[uuid.UUID] = []
    for item in values:
        out.append(parse_uuid(item, field_name=field_name))
    # Stable unique order
    seen: set[uuid.UUID] = set()
    unique: list[uuid.UUID] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return tuple(unique)


def reject_freeform_filter(raw: object) -> None:
    """Browser-supplied Qdrant filter objects are never accepted."""
    if raw is None:
        return
    raise InvalidRetrievalFilter(
        "Free-form Qdrant filters are not accepted; scope is resolved server-side.",
        details={"error_kind": "freeform_filter_rejected"},
    )


def build_tenant_scope(
    *,
    workspace_id: uuid.UUID | str,
    video_ids: list[uuid.UUID | str] | tuple[uuid.UUID | str, ...],
) -> TenantScopeFilter:
    ws = parse_uuid(workspace_id, field_name="workspace_id")
    vids = parse_uuid_list(list(video_ids), field_name="video_ids")
    if not vids:
        raise InvalidRetrievalFilter(
            "Authorized video_ids must be non-empty for retrieval.",
            details={"field": "video_ids"},
        )
    return TenantScopeFilter(workspace_id=ws, video_ids=vids)


def payload_matches_scope(payload: dict[str, Any], scope: TenantScopeFilter) -> bool:
    try:
        ws = parse_uuid(payload.get("workspace_id"), field_name="workspace_id")
        vid = parse_uuid(payload.get("video_id"), field_name="video_id")
    except InvalidRetrievalFilter:
        return False
    if ws != scope.workspace_id:
        return False
    return vid in scope.video_ids
