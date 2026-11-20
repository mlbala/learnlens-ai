"""Typed retrieval / indexing errors — no secrets or raw upstream bodies."""

from __future__ import annotations

from typing import Any


class RetrievalError(Exception):
    code: str = "RETRIEVAL_ERROR"
    retryable: bool = False
    http_status: int = 502

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class VectorStoreUnavailable(RetrievalError):
    """Qdrant Cloud unreachable, suspended, or misconfigured."""

    code = "VECTOR_STORE_UNAVAILABLE"
    retryable = True
    http_status = 503


class VectorStoreConfigurationError(RetrievalError):
    """Missing Qdrant credentials or unsupported backend."""

    code = "VECTOR_STORE_CONFIGURATION_ERROR"
    retryable = False
    http_status = 503


class EmbeddingProfileMismatch(RetrievalError):
    """Attempt to mix dimensions / profiles in one collection."""

    code = "EMBEDDING_PROFILE_MISMATCH"
    retryable = False
    http_status = 409

    def __init__(
        self,
        message: str,
        *,
        expected_profile: str,
        actual_profile: str | None = None,
        expected_dimensions: int | None = None,
        actual_dimensions: int | None = None,
    ) -> None:
        details: dict[str, Any] = {
            "expected_profile": expected_profile,
            "reindex_required": True,
        }
        if actual_profile is not None:
            details["actual_profile"] = actual_profile
        if expected_dimensions is not None:
            details["expected_dimensions"] = expected_dimensions
        if actual_dimensions is not None:
            details["actual_dimensions"] = actual_dimensions
        super().__init__(message, details=details)


class UnauthorizedScopeError(RetrievalError):
    """Caller-supplied scope is outside the authenticated workspace."""

    code = "UNAUTHORIZED_SCOPE"
    retryable = False
    http_status = 403


class InvalidRetrievalFilter(RetrievalError):
    """Rejected free-form or non-UUID filter input."""

    code = "INVALID_RETRIEVAL_FILTER"
    retryable = False
    http_status = 400
