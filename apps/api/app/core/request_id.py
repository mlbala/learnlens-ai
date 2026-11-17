"""Request ID middleware — structured correlation without logging secrets."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger("learnlens.request")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to every request/response and structured log line."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        request_id = incoming or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response
