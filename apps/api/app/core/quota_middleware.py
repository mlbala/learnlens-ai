"""Quota middleware — fail closed on workspace spend/request caps for costly routes."""

from __future__ import annotations

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.errors import error_body
from app.core.settings import Settings
from app.services.usage import WorkspaceQuotaExceeded, current_period

# Paths that can incur provider spend or durable jobs (POST/PUT only).
_COSTLY_PREFIXES = (
    "/api/v1/chat/",
    "/api/v1/videos/",
    "/api/v1/playlists/",
)


class QuotaMiddleware(BaseHTTPMiddleware):
    """
    Soft gate: if a prior dependency attached `request.state.workspace_id` and
    `request.state.usage_blocked`, reject. Expensive handlers also call UsageService
    directly — this middleware centralizes the 429 response shape.
    """

    def __init__(self, app, settings: Settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.usage_period = current_period()
        path = request.url.path
        method = request.method.upper()
        if method in {"POST", "PUT", "PATCH"} and any(
            path.startswith(p) for p in _COSTLY_PREFIXES
        ):
            blocked = getattr(request.state, "usage_blocked", None)
            if isinstance(blocked, WorkspaceQuotaExceeded):
                request_id = getattr(request.state, "request_id", None)
                return JSONResponse(
                    status_code=429,
                    content=error_body(
                        code=blocked.code,
                        message=blocked.message,
                        request_id=request_id,
                        details={"period": request.state.usage_period},
                    ),
                )
        return await call_next(request)
