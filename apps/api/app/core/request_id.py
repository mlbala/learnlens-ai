"""Request ID + trace correlation middleware — structured logs without secrets."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.observability.tracing import (
    REQUEST_ID_HEADER,
    TRACE_ID_HEADER,
    TRACEPARENT_HEADER,
    bind_context,
    clear_context,
    format_traceparent,
    parse_traceparent,
    start_span,
)

logger = logging.getLogger("learnlens.request")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach request/trace IDs and an OTEL-compatible request span."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        request_id = incoming or str(uuid.uuid4())

        parsed = parse_traceparent(request.headers.get(TRACEPARENT_HEADER))
        header_trace = request.headers.get(TRACE_ID_HEADER, "").strip()
        if parsed:
            trace_id, parent_span_id = parsed
        else:
            trace_id = header_trace or uuid.uuid4().hex
            parent_span_id = None

        ctx = bind_context(
            request_id=request_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        request.state.request_id = request_id
        request.state.trace_id = ctx.trace_id

        with start_span(
            "http.request",
            http_method=request.method,
            http_route=request.url.path,
        ) as span:
            try:
                response = await call_next(request)
            except Exception:
                span.record_error("HTTP_HANDLER_ERROR")
                clear_context()
                raise

            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers[TRACE_ID_HEADER] = ctx.trace_id
            response.headers[TRACEPARENT_HEADER] = format_traceparent(
                ctx.trace_id, span.context.span_id
            )
            span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= 500:
                span.record_error("HTTP_5XX")
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "trace_id": ctx.trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )
            clear_context()
            return response
