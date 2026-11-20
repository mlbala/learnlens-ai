"""Liveness and readiness endpoints for Neon + Qdrant Cloud + optional Redis."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.core.health import check_neon, check_qdrant, check_redis
from app.core.observability.metrics import get_worker_metrics
from app.core.settings import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def health_live(request: Request) -> dict[str, Any]:
    """Process is up. Does not touch Neon, Qdrant, or AI providers."""
    request_id = getattr(request.state, "request_id", None)
    return {
        "status": "ok",
        "request_id": request_id,
        "trace_id": getattr(request.state, "trace_id", None),
    }


@router.get("/health/ready")
async def health_ready(request: Request, response: Response) -> dict[str, Any]:
    """Ready when Neon and Qdrant Cloud both respond. No paid AI calls."""
    settings: Settings = get_settings()
    neon = await check_neon(settings)
    qdrant = check_qdrant(settings)
    redis = check_redis(settings)
    # Redis is required only when Celery is not eager (real worker topology).
    redis_required = not settings.celery_task_always_eager
    ready = bool(neon.get("ok") and qdrant.get("ok") and (redis.get("ok") or not redis_required))
    request_id = getattr(request.state, "request_id", None)
    body = {
        "status": "ok" if ready else "degraded",
        "request_id": request_id,
        "trace_id": getattr(request.state, "trace_id", None),
        "checks": {
            "neon": neon,
            "qdrant": qdrant,
            "redis": redis,
        },
        "worker_metrics": get_worker_metrics().snapshot(),
    }
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return body
