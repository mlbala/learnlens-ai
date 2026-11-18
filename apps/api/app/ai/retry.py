"""Bounded async retry with exponential backoff for retryable provider errors."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.ai.errors import ProviderError, ProviderResponseInvalid, ProviderTemporarilyUnavailable

logger = logging.getLogger(__name__)


async def with_bounded_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    base_delay_seconds: float = 0.05,
    provider: str | None = None,
    schema_clarification: Callable[[], Awaitable[T]] | None = None,
) -> T:
    """
    Retry retryable provider errors up to max_retries times.

    Malformed structured responses get at most one schema-clarification attempt
    (via schema_clarification), then fail closed — never switch providers.
    """
    attempts = 0
    last_error: ProviderError | None = None
    clarification_used = False

    while attempts <= max_retries:
        try:
            return await operation()
        except ProviderResponseInvalid as exc:
            last_error = exc
            if clarification_used or schema_clarification is None:
                raise
            clarification_used = True
            logger.info(
                "provider_schema_clarification",
                extra={"provider": provider or exc.provider, "attempt": attempts},
            )
            try:
                return await schema_clarification()
            except ProviderError:
                raise
        except ProviderTemporarilyUnavailable as exc:
            last_error = exc
            if attempts >= max_retries:
                raise
            delay = base_delay_seconds * (2**attempts)
            logger.info(
                "provider_retry_backoff",
                extra={
                    "provider": provider or exc.provider,
                    "attempt": attempts,
                    "delay_seconds": delay,
                    "code": exc.code,
                },
            )
            await asyncio.sleep(delay)
            attempts += 1
        except ProviderError:
            # Non-retryable (401, refusal, config) — fail immediately.
            raise

    assert last_error is not None
    raise last_error
