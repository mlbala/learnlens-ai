"""Lightweight OpenTelemetry-compatible tracing (in-process; no paid exporters)."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from app.core.observability.sanitize import sanitize_span_attributes

logger = logging.getLogger("learnlens.trace")

# W3C-ish headers we accept/propagate (compatible with OTEL HTTP propagators).
TRACEPARENT_HEADER = "traceparent"
REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"


@dataclass(slots=True)
class SpanContext:
    trace_id: str
    span_id: str
    request_id: str
    parent_span_id: str | None = None


@dataclass
class Span:
    name: str
    context: SpanContext
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error_code: str | None = None
    started_ns: int = field(default_factory=time.time_ns)
    ended_ns: int | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        safe = sanitize_span_attributes({key: value})
        self.attributes.update(safe)

    def record_error(self, code: str, *, message: str | None = None) -> None:
        self.status = "error"
        self.error_code = code
        if message:
            self.set_attribute("error.message", message[:200])

    def end(self) -> None:
        self.ended_ns = time.time_ns()
        duration_ms = ((self.ended_ns or self.started_ns) - self.started_ns) / 1_000_000
        logger.info(
            "span_finished",
            extra={
                "span_name": self.name,
                "trace_id": self.context.trace_id,
                "span_id": self.context.span_id,
                "parent_span_id": self.context.parent_span_id,
                "request_id": self.context.request_id,
                "status": self.status,
                "error_code": self.error_code,
                "duration_ms": round(duration_ms, 3),
                "attributes": sanitize_span_attributes(self.attributes),
            },
        )

    def to_otel_dict(self) -> dict[str, Any]:
        """Serialize in a shape compatible with OTEL span JSON exporters."""
        return {
            "name": self.name,
            "context": {
                "trace_id": self.context.trace_id,
                "span_id": self.context.span_id,
                "trace_flags": "01",
            },
            "parent_id": self.context.parent_span_id,
            "start_time_unix_nano": self.started_ns,
            "end_time_unix_nano": self.ended_ns,
            "status": {"code": "ERROR" if self.status == "error" else "OK"},
            "attributes": sanitize_span_attributes(self.attributes),
        }


_current: ContextVar[SpanContext | None] = ContextVar("learnlens_span_ctx", default=None)
_recent_spans: list[dict[str, Any]] = []
_MAX_RECENT = 200


def _new_trace_id() -> str:
    return uuid.uuid4().hex


def _new_span_id() -> str:
    return uuid.uuid4().hex[:16]


def parse_traceparent(value: str | None) -> tuple[str, str] | None:
    """Parse `version-traceid-spanid-flags` (W3C). Returns (trace_id, parent_span_id)."""
    if not value:
        return None
    parts = value.strip().split("-")
    if len(parts) != 4:
        return None
    version, trace_id, parent_span_id, _flags = parts
    if version != "00" or len(trace_id) != 32 or len(parent_span_id) != 16:
        return None
    if trace_id == "0" * 32 or parent_span_id == "0" * 16:
        return None
    return trace_id, parent_span_id


def format_traceparent(trace_id: str, span_id: str) -> str:
    return f"00-{trace_id}-{span_id}-01"


def get_span_context() -> SpanContext | None:
    return _current.get()


def get_request_id() -> str | None:
    ctx = _current.get()
    return ctx.request_id if ctx else None


def get_trace_id() -> str | None:
    ctx = _current.get()
    return ctx.trace_id if ctx else None


def bind_context(
    *,
    request_id: str,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> SpanContext:
    ctx = SpanContext(
        trace_id=trace_id or _new_trace_id(),
        span_id=_new_span_id(),
        request_id=request_id,
        parent_span_id=parent_span_id,
    )
    _current.set(ctx)
    return ctx


def clear_context() -> None:
    _current.set(None)


@contextmanager
def start_span(name: str, **attributes: Any) -> Iterator[Span]:
    parent = _current.get()
    if parent is None:
        request_id = str(uuid.uuid4())
        ctx = SpanContext(
            trace_id=_new_trace_id(),
            span_id=_new_span_id(),
            request_id=request_id,
        )
    else:
        ctx = SpanContext(
            trace_id=parent.trace_id,
            span_id=_new_span_id(),
            request_id=parent.request_id,
            parent_span_id=parent.span_id,
        )
    token = _current.set(ctx)
    span = Span(name=name, context=ctx, attributes=sanitize_span_attributes(attributes))
    try:
        yield span
    except Exception as exc:
        span.record_error(type(exc).__name__, message=str(exc)[:200])
        raise
    finally:
        span.end()
        _recent_spans.append(span.to_otel_dict())
        if len(_recent_spans) > _MAX_RECENT:
            del _recent_spans[: len(_recent_spans) - _MAX_RECENT]
        _current.reset(token)


def recent_spans_for_tests() -> list[dict[str, Any]]:
    """Test helper — returns recent finished spans (no PII by construction)."""
    return list(_recent_spans)


def reset_spans_for_tests() -> None:
    _recent_spans.clear()
    clear_context()


def celery_headers_from_context() -> dict[str, str]:
    """Headers to attach when enqueueing Celery tasks for correlation."""
    ctx = _current.get()
    if ctx is None:
        request_id = str(uuid.uuid4())
        trace_id = _new_trace_id()
        span_id = _new_span_id()
        return {
            REQUEST_ID_HEADER: request_id,
            TRACE_ID_HEADER: trace_id,
            TRACEPARENT_HEADER: format_traceparent(trace_id, span_id),
        }
    return {
        REQUEST_ID_HEADER: ctx.request_id,
        TRACE_ID_HEADER: ctx.trace_id,
        TRACEPARENT_HEADER: format_traceparent(ctx.trace_id, ctx.span_id),
    }


def bind_from_celery_headers(headers: dict[str, Any] | None) -> SpanContext:
    headers = headers or {}
    request_id = str(headers.get(REQUEST_ID_HEADER) or headers.get("request_id") or uuid.uuid4())
    traceparent = headers.get(TRACEPARENT_HEADER) or headers.get("traceparent")
    parsed = parse_traceparent(str(traceparent) if traceparent else None)
    if parsed:
        trace_id, parent_span_id = parsed
    else:
        trace_id = str(headers.get(TRACE_ID_HEADER) or headers.get("trace_id") or _new_trace_id())
        parent_span_id = None
    return bind_context(
        request_id=request_id,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )
