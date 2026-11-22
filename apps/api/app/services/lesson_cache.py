"""Redis cache for a saved lesson body. Snippets and vector hits stay out."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

LESSON_BODY_TTL_SECONDS = 600


class LessonBodyCache(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...

    def put(self, key: str, payload: dict[str, Any]) -> None: ...

    def delete_prefix(self, prefix: str) -> None: ...


@dataclass(frozen=True)
class CachedSegment:
    id: uuid.UUID
    ordinal: int
    text: str
    content_hash: str
    start_ms: int | None
    end_ms: int | None
    evidence_origin: str
    evidence_provider: str


def _millis(value: object) -> int | None:
    return value if isinstance(value, int) else None


def lesson_body_key(workspace_id: uuid.UUID, video_id: uuid.UUID, content_hash: str) -> str:
    return f"ll:lesson-body:{workspace_id}:{video_id}:{content_hash}"


def lesson_body_prefix(workspace_id: uuid.UUID, video_id: uuid.UUID) -> str:
    return f"ll:lesson-body:{workspace_id}:{video_id}:"


def lesson_body_cache_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep the saved lesson body. Drop outside snippets, titles, URLs, and hits."""
    points = raw.get("key_points")
    key_points = (
        [str(point) for point in points if str(point).strip()]
        if isinstance(points, list)
        else []
    )
    segments: list[dict[str, Any]] = []
    rows = raw.get("segments")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            segments.append(
                {
                    "id": str(row.get("id") or ""),
                    "ordinal": int(row.get("ordinal") or 0),
                    "text": str(row.get("text") or ""),
                    "content_hash": str(row.get("content_hash") or ""),
                    "start_ms": _millis(row.get("start_ms")),
                    "end_ms": _millis(row.get("end_ms")),
                    "evidence_origin": str(row.get("evidence_origin") or ""),
                    "evidence_provider": str(row.get("evidence_provider") or ""),
                }
            )
    return {
        "summary": str(raw.get("summary") or ""),
        "key_points": key_points,
        "segments": segments,
    }


def lesson_body_from_rows(
    summary: str,
    key_points: list[str],
    segments: list[Any],
) -> dict[str, Any]:
    return lesson_body_cache_payload(
        {
            "summary": summary,
            "key_points": key_points,
            "segments": [
                {
                    "id": row.id,
                    "ordinal": row.ordinal,
                    "text": row.text,
                    "content_hash": row.content_hash,
                    "start_ms": row.start_ms,
                    "end_ms": row.end_ms,
                    "evidence_origin": row.evidence_origin,
                    "evidence_provider": row.evidence_provider,
                }
                for row in segments
            ],
        }
    )


def segments_from_body(payload: dict[str, Any]) -> list[CachedSegment]:
    rows: list[CachedSegment] = []
    for item in payload.get("segments") or []:
        if not isinstance(item, dict):
            continue
        try:
            segment_id = uuid.UUID(str(item.get("id")))
        except ValueError:
            continue
        rows.append(
            CachedSegment(
                id=segment_id,
                ordinal=int(item.get("ordinal") or 0),
                text=str(item.get("text") or ""),
                content_hash=str(item.get("content_hash") or ""),
                start_ms=item.get("start_ms") if isinstance(item.get("start_ms"), int) else None,
                end_ms=item.get("end_ms") if isinstance(item.get("end_ms"), int) else None,
                evidence_origin=str(item.get("evidence_origin") or ""),
                evidence_provider=str(item.get("evidence_provider") or ""),
            )
        )
    return rows


def cache_get(cache: LessonBodyCache | None, key: str) -> dict[str, Any] | None:
    if cache is None:
        return None
    try:
        hit = cache.get(key)
    except Exception as exc:  # noqa: BLE001 — Redis down reads Neon
        logger.info("lesson_cache_unavailable", extra={"error_type": type(exc).__name__})
        return None
    if not isinstance(hit, dict) or "summary" not in hit or "segments" not in hit:
        return None
    return lesson_body_cache_payload(hit)


def cache_put(cache: LessonBodyCache | None, key: str, payload: dict[str, Any]) -> None:
    if cache is None:
        return
    body = lesson_body_cache_payload(payload)
    try:
        cache.put(key, body)
    except Exception as exc:  # noqa: BLE001 — a failed write must not block the lesson
        logger.info("lesson_cache_unavailable", extra={"error_type": type(exc).__name__})


def cache_delete_prefix(cache: LessonBodyCache | None, prefix: str) -> None:
    if cache is None:
        return
    try:
        cache.delete_prefix(prefix)
    except Exception as exc:  # noqa: BLE001 — trim still deletes Neon and Qdrant
        logger.info("lesson_cache_delete_failed", extra={"error_type": type(exc).__name__})


def read_lesson_body(
    cache: LessonBodyCache | None,
    key: str,
    load_neon: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Return a cached lesson body, or the Neon body when Redis misses or fails."""
    cached = cache_get(cache, key)
    if cached is not None:
        return cached
    body = lesson_body_cache_payload(load_neon())
    cache_put(cache, key, body)
    return body


def lesson_cache_from_settings(settings: Any) -> LessonBodyCache | None:
    if settings is None or not bool(getattr(settings, "lesson_body_cache_enabled", False)):
        return None
    url = str(getattr(settings, "redis_url", "") or "").strip()
    if not url:
        return None
    return RedisLessonBodyCache(url)


class RedisLessonBodyCache:
    """Short TTL. Connection failures propagate so callers can fall back to Neon."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Any = None

    def _redis(self) -> Any:
        if self._client is None:
            import redis

            self._client = redis.Redis.from_url(
                self._url,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
                decode_responses=True,
            )
        return self._client

    def get(self, key: str) -> dict[str, Any] | None:
        raw = self._redis().get(key)
        if not raw:
            return None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return lesson_body_cache_payload(parsed)

    def put(self, key: str, payload: dict[str, Any]) -> None:
        body = lesson_body_cache_payload(payload)
        client = self._redis()
        client.set(key, json.dumps(body, separators=(",", ":")), ex=LESSON_BODY_TTL_SECONDS)
        prefix = key.rsplit(":", 1)[0] + ":"
        index = f"{prefix}index"
        client.sadd(index, key)
        client.expire(index, LESSON_BODY_TTL_SECONDS)

    def delete_prefix(self, prefix: str) -> None:
        client = self._redis()
        index = f"{prefix}index"
        members = list(client.smembers(index) or [])
        if members:
            client.delete(*members)
        client.delete(index)
