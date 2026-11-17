"""Liveness and readiness endpoints for Neon + Qdrant Cloud."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.core.health import check_neon, check_qdrant
from app.core.settings import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def health_live(request: Request) -> dict[str, Any]:
    """Process is up. Does not touch Neon, Qdrant, or AI providers."""
    request_id = getattr(request.state, "request_id", None)
    return {"status": "ok", "request_id": request_id}


@router.get("/health/ready")
async def health_ready(request: Request, response: Response) -> dict[str, Any]:
    """Ready when Neon and Qdrant Cloud both respond. No paid AI calls."""
    settings: Settings = get_settings()
    neon = await check_neon(settings)
    qdrant = check_qdrant(settings)
    ready = bool(neon.get("ok") and qdrant.get("ok"))
    request_id = getattr(request.state, "request_id", None)
    body = {
        "status": "ok" if ready else "degraded",
        "request_id": request_id,
        "checks": {
            "neon": neon,
            "qdrant": qdrant,
        },
    }
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return body
