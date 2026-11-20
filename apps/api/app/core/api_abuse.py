"""General API rate-limit middleware (per client IP; health exempt)."""

from __future__ import annotations

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core import rate_limit as rate_limit_mod
from app.core.errors import error_body
from app.core.settings import Settings

_EXEMPT_PREFIXES = ("/health",)


class ApiAbuseMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)
        # Auth routes keep the dedicated auth limiter; skip double-counting here.
        if path.startswith("/api/v1/auth/"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        # Look up module attribute so configure_api_rate_limiter() takes effect.
        if not rate_limit_mod.api_rate_limiter.allow(f"api:{client}"):
            request_id = getattr(request.state, "request_id", None)
            return JSONResponse(
                status_code=429,
                content=error_body(
                    code="RATE_LIMITED",
                    message="Too many requests. Try again later.",
                    request_id=request_id,
                ),
            )
        return await call_next(request)
