"""Provider circuit breaker for timeouts / rate limits (fail closed when open)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.ai.errors import ProviderError, ProviderTemporarilyUnavailable


class CircuitOpenError(ProviderTemporarilyUnavailable):
    """Raised when the breaker is open — maps to PROVIDER_CIRCUIT_OPEN."""

    code = "PROVIDER_CIRCUIT_OPEN"

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message, provider=provider, details={"error_kind": "circuit_open"})


@dataclass
class _BreakerState:
    failures: int = 0
    opened_at: float | None = None
    half_open: bool = False


class CircuitBreaker:
    """
    Simple consecutive-failure breaker.

    - Opens after `failure_threshold` retryable failures.
    - Stays open for `recovery_timeout_seconds`, then allows one half-open probe.
    - Success in half-open / closed resets the counter.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
    ) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._recovery_timeout = recovery_timeout_seconds
        self._lock = threading.Lock()
        self._states: dict[str, _BreakerState] = {}

    def _state(self, key: str) -> _BreakerState:
        if key not in self._states:
            self._states[key] = _BreakerState()
        return self._states[key]

    def before_call(self, key: str) -> None:
        with self._lock:
            state = self._state(key)
            if state.opened_at is None:
                return
            elapsed = time.monotonic() - state.opened_at
            if elapsed < self._recovery_timeout:
                raise CircuitOpenError(
                    f"Circuit open for '{key}' — retry after cooldown.",
                    provider=key,
                )
            # Half-open probe window.
            state.half_open = True

    def record_success(self, key: str) -> None:
        with self._lock:
            self._states[key] = _BreakerState()

    def record_failure(self, key: str, *, retryable: bool) -> None:
        with self._lock:
            state = self._state(key)
            if not retryable:
                # Non-retryable (401/config) — do not trip the breaker.
                return
            state.failures += 1
            if state.half_open or state.failures >= self._failure_threshold:
                state.opened_at = time.monotonic()
                state.half_open = False

    def is_open(self, key: str) -> bool:
        with self._lock:
            state = self._state(key)
            if state.opened_at is None:
                return False
            return (time.monotonic() - state.opened_at) < self._recovery_timeout

    def reset(self) -> None:
        with self._lock:
            self._states.clear()


_breaker = CircuitBreaker()


def get_circuit_breaker() -> CircuitBreaker:
    return _breaker


def configure_circuit_breaker(
    *,
    failure_threshold: int = 3,
    recovery_timeout_seconds: float = 30.0,
) -> CircuitBreaker:
    global _breaker
    _breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout_seconds=recovery_timeout_seconds,
    )
    return _breaker


async def call_with_circuit(
    key: str,
    operation,
    *,
    breaker: CircuitBreaker | None = None,
):
    """Run an async operation behind the circuit breaker."""
    cb = breaker or get_circuit_breaker()
    cb.before_call(key)
    try:
        result = await operation()
    except ProviderError as exc:
        cb.record_failure(key, retryable=exc.retryable)
        raise
    except Exception:
        cb.record_failure(key, retryable=True)
        raise
    else:
        cb.record_success(key)
        return result
