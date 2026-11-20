"""Stable error taxonomy for ops dashboards and actionable job failure codes."""

from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    AUTH = "auth"
    QUOTA = "quota"
    VALIDATION = "validation"
    PROVIDER = "provider"
    STORAGE = "storage"
    DEPENDENCY = "dependency"
    JOB = "job"
    INTERNAL = "internal"


# Map known public error codes → category + whether operator action is needed.
_TAXONOMY: dict[str, tuple[ErrorCategory, bool, str]] = {
    "UNAUTHENTICATED": (ErrorCategory.AUTH, False, "Sign in again."),
    "FORBIDDEN": (ErrorCategory.AUTH, False, "Check workspace membership."),
    "CSRF_FAILED": (ErrorCategory.AUTH, False, "Refresh the page and retry."),
    "USAGE_QUOTA_EXCEEDED": (
        ErrorCategory.QUOTA,
        True,
        "Raise workspace caps or wait for the period to reset.",
    ),
    "WORKSPACE_TOKEN_QUOTA_EXCEEDED": (
        ErrorCategory.QUOTA,
        True,
        "Token budget exhausted for this period.",
    ),
    "WORKSPACE_JOB_QUOTA_EXCEEDED": (
        ErrorCategory.QUOTA,
        True,
        "Job budget exhausted for this period.",
    ),
    "WORKSPACE_SPEND_QUOTA_EXCEEDED": (
        ErrorCategory.QUOTA,
        True,
        "Estimated spend cap reached for this period.",
    ),
    "PROVIDER_CONFIGURATION_ERROR": (
        ErrorCategory.PROVIDER,
        True,
        "Fix provider credentials / allowlist; do not retry blindly.",
    ),
    "PROVIDER_TEMPORARILY_UNAVAILABLE": (
        ErrorCategory.PROVIDER,
        True,
        "Provider timeout or rate limit — circuit may be open; retry later.",
    ),
    "PROVIDER_REFUSED": (ErrorCategory.PROVIDER, False, "Content refused by provider policy."),
    "PROVIDER_RESPONSE_INVALID": (
        ErrorCategory.PROVIDER,
        True,
        "Model returned invalid structured output.",
    ),
    "PROVIDER_CIRCUIT_OPEN": (
        ErrorCategory.PROVIDER,
        True,
        "Circuit breaker open after repeated provider failures.",
    ),
    "DATABASE_UNAVAILABLE": (
        ErrorCategory.DEPENDENCY,
        True,
        "Neon connectivity failed — check DATABASE_URL / project status.",
    ),
    "QDRANT_UNAVAILABLE": (
        ErrorCategory.DEPENDENCY,
        True,
        "Qdrant Cloud unreachable — reactivate cluster if suspended.",
    ),
    "REDIS_UNAVAILABLE": (
        ErrorCategory.DEPENDENCY,
        True,
        "Redis broker unreachable — workers cannot dequeue.",
    ),
    "TRANSCRIPT_JOB_FAILED": (ErrorCategory.JOB, True, "Inspect job stage and last_error_code."),
    "JOB_DEAD_LETTER": (
        ErrorCategory.JOB,
        True,
        "Retries exhausted — recover manually or re-enqueue with a new idempotency key.",
    ),
    "JOB_LEASE_EXPIRED": (
        ErrorCategory.JOB,
        True,
        "Worker lease expired; recovery requeued the job.",
    ),
    "SOURCE_TRANSCRIPT_REQUIRED": (
        ErrorCategory.VALIDATION,
        False,
        "Upload an authorized transcript before summarizing.",
    ),
    "PAYLOAD_TOO_LARGE": (ErrorCategory.VALIDATION, False, "Reduce upload size."),
    "RIGHTS_ATTESTATION_REQUIRED": (
        ErrorCategory.VALIDATION,
        False,
        "Attest rights before upload.",
    ),
    "STORAGE_OBJECT_MISSING": (
        ErrorCategory.STORAGE,
        True,
        "Object missing from private storage.",
    ),
}


def classify_error(code: str) -> dict[str, str | bool]:
    """Return taxonomy metadata for a public error / job failure code."""
    category, actionable, guidance = _TAXONOMY.get(
        code,
        (ErrorCategory.INTERNAL, True, "Inspect logs with request_id; fail closed."),
    )
    return {
        "code": code,
        "category": str(category),
        "actionable": actionable,
        "operator_guidance": guidance,
    }


def is_retryable_provider_code(code: str) -> bool:
    return code in {
        "PROVIDER_TEMPORARILY_UNAVAILABLE",
        "PROVIDER_CIRCUIT_OPEN",
    }
