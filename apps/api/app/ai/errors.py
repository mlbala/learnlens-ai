"""Typed provider errors — never include secrets or raw provider bodies in public messages."""

from __future__ import annotations

from typing import Any


class ProviderError(Exception):
    """Base provider failure. `code` maps to API error codes."""

    code: str = "PROVIDER_ERROR"
    retryable: bool = False
    http_status: int = 502

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.details = details or {}

    def public_details(self) -> dict[str, Any]:
        """Safe details for API responses (no secrets / raw upstream bodies)."""
        out: dict[str, Any] = {}
        if self.provider:
            out["provider"] = self.provider
        for key in ("error_kind", "status_code", "reindex_required"):
            if key in self.details:
                out[key] = self.details[key]
        return out


class ProviderConfigurationError(ProviderError):
    """Missing/invalid credentials or allowlist (401-class). Never retry."""

    code = "PROVIDER_CONFIGURATION_ERROR"
    retryable = False
    http_status = 503


class ProviderTemporarilyUnavailable(ProviderError):
    """Rate limit / 5xx / timeout — bounded retry then fail."""

    code = "PROVIDER_TEMPORARILY_UNAVAILABLE"
    retryable = True
    http_status = 503


class ProviderRefused(ProviderError):
    """Content safety / policy refusal from the vendor."""

    code = "PROVIDER_REFUSED"
    retryable = False
    http_status = 422


class ProviderResponseInvalid(ProviderError):
    """Malformed / empty structured output after validation retries."""

    code = "PROVIDER_RESPONSE_INVALID"
    retryable = False
    http_status = 502


class EmbeddingDimensionMismatch(ProviderError):
    """Vector length does not match the configured embedding profile."""

    code = "EMBEDDING_DIMENSION_MISMATCH"
    retryable = False
    http_status = 409

    def __init__(
        self,
        message: str,
        *,
        expected: int,
        actual: int,
        provider: str | None = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            details={
                "expected_dimensions": expected,
                "actual_dimensions": actual,
                "reindex_required": True,
            },
        )
        self.expected = expected
        self.actual = actual


class ProviderNotSupported(ProviderError):
    """Requested provider/model is not allowlisted or not implemented."""

    code = "PROVIDER_NOT_SUPPORTED"
    retryable = False
    http_status = 400
