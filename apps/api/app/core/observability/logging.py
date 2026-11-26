"""Structured JSON logging with request/trace correlation fields."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.observability.sanitize import sanitize_span_attributes
from app.core.observability.tracing import get_request_id, get_trace_id

# Extra keys we lift into the JSON root when present on LogRecord.
_CORRELATION_KEYS = (
    "request_id",
    "trace_id",
    "span_id",
    "span_name",
    "parent_span_id",
    "job_id",
    "workspace_id",
    "method",
    "path",
    "status_code",
    "error_code",
    "duration_ms",
    "db_queries",
    "db_ms",
    "attributes",
)


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log line (no raw transcript / secrets)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or get_request_id()
        trace_id = getattr(record, "trace_id", None) or get_trace_id()
        if request_id:
            payload["request_id"] = request_id
        if trace_id:
            payload["trace_id"] = trace_id

        for key in _CORRELATION_KEYS:
            if key in ("request_id", "trace_id"):
                continue
            if hasattr(record, key):
                value = getattr(record, key)
                if value is not None:
                    payload[key] = value

        if record.exc_info:
            payload["exc_type"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else None
            )

        # Never allow accidental large / sensitive extras through.
        if "attributes" in payload and isinstance(payload["attributes"], dict):
            payload["attributes"] = sanitize_span_attributes(payload["attributes"])

        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_structured_logging(*, level: str = "INFO", json_logs: bool = True) -> None:
    """Replace root handlers with a structured (JSON) or text formatter."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
