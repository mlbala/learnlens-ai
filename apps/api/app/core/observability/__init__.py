"""Observability: tracing, structured logs, metrics, cost estimates, reliability."""

from app.core.observability.circuit_breaker import (
    CircuitOpenError,
    call_with_circuit,
    configure_circuit_breaker,
    get_circuit_breaker,
)
from app.core.observability.cost import (
    COST_ESTIMATE_DISCLAIMER,
    COST_ESTIMATE_VERSION,
    CostEstimate,
    estimate_provider_cost,
)
from app.core.observability.dead_letter import DeadLetterDecision, evaluate_retry
from app.core.observability.error_taxonomy import ErrorCategory, classify_error
from app.core.observability.logging import configure_structured_logging
from app.core.observability.metrics import WorkerMetrics, get_worker_metrics
from app.core.observability.sanitize import sanitize_span_attributes
from app.core.observability.tracing import (
    REQUEST_ID_HEADER,
    TRACE_ID_HEADER,
    TRACEPARENT_HEADER,
    bind_context,
    bind_from_celery_headers,
    celery_headers_from_context,
    get_request_id,
    get_span_context,
    get_trace_id,
    start_span,
)

__all__ = [
    "COST_ESTIMATE_DISCLAIMER",
    "COST_ESTIMATE_VERSION",
    "CircuitOpenError",
    "CostEstimate",
    "DeadLetterDecision",
    "ErrorCategory",
    "REQUEST_ID_HEADER",
    "TRACE_ID_HEADER",
    "TRACEPARENT_HEADER",
    "WorkerMetrics",
    "bind_context",
    "bind_from_celery_headers",
    "call_with_circuit",
    "celery_headers_from_context",
    "classify_error",
    "configure_circuit_breaker",
    "configure_structured_logging",
    "estimate_provider_cost",
    "evaluate_retry",
    "get_circuit_breaker",
    "get_request_id",
    "get_span_context",
    "get_trace_id",
    "get_worker_metrics",
    "sanitize_span_attributes",
    "start_span",
]
