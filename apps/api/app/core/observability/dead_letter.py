"""Dead-letter policy after bounded retries — actionable failure, not silent drop."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.observability.error_taxonomy import classify_error
from app.core.observability.metrics import get_worker_metrics

logger = logging.getLogger("learnlens.dead_letter")


@dataclass(frozen=True, slots=True)
class DeadLetterDecision:
    dead_letter: bool
    error_code: str
    taxonomy: dict[str, Any]
    should_retry: bool


def evaluate_retry(
    *,
    attempt: int,
    max_attempts: int,
    error_code: str,
    retryable: bool,
    queue: str = "default",
) -> DeadLetterDecision:
    """
    Decide retry vs dead-letter.

    Exactly-once *effects* are achieved via unique idempotency keys at the domain
    layer — this policy does not promise exactly-once *execution*.
    """
    taxonomy = classify_error(error_code)
    if retryable and attempt < max_attempts:
        return DeadLetterDecision(
            dead_letter=False,
            error_code=error_code,
            taxonomy=taxonomy,
            should_retry=True,
        )

    final_code = error_code if not retryable else "JOB_DEAD_LETTER"
    taxonomy = classify_error(final_code)
    get_worker_metrics().record_dead_letter(queue)
    logger.warning(
        "job_dead_lettered",
        extra={
            "error_code": final_code,
            "original_error_code": error_code,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "category": taxonomy["category"],
            "actionable": taxonomy["actionable"],
        },
    )
    return DeadLetterDecision(
        dead_letter=True,
        error_code=final_code,
        taxonomy=taxonomy,
        should_retry=False,
    )
