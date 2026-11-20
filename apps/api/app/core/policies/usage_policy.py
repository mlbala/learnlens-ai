"""UsagePolicy — per-user daily caps for jobs/chat (in-process; fail closed)."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import date


class UsageQuotaExceeded(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class UsageLimits:
    daily_chat_messages: int
    daily_transcript_jobs: int
    daily_media_jobs: int = 10


class UsagePolicy:
    """
    Sliding calendar-day counters keyed by user id.

    Process-local by design for MVP offline tests; production can swap a Redis backend
    without changing call sites. Guardrails are multilayered — this is not a spend ceiling.
    """

    def __init__(self, limits: UsageLimits) -> None:
        self._limits = limits
        self._lock = threading.Lock()
        self._chat: dict[tuple[str, str], int] = defaultdict(int)
        self._jobs: dict[tuple[str, str], int] = defaultdict(int)
        self._media_jobs: dict[tuple[str, str], int] = defaultdict(int)

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    def check_chat_allowed(self, user_id: str) -> None:
        key = (user_id, self._today())
        with self._lock:
            if self._chat[key] >= self._limits.daily_chat_messages:
                raise UsageQuotaExceeded(
                    "USAGE_QUOTA_EXCEEDED",
                    "Daily chat message quota exceeded.",
                )

    def record_chat(self, user_id: str) -> None:
        key = (user_id, self._today())
        with self._lock:
            self._chat[key] += 1

    def check_job_allowed(self, user_id: str) -> None:
        key = (user_id, self._today())
        with self._lock:
            if self._jobs[key] >= self._limits.daily_transcript_jobs:
                raise UsageQuotaExceeded(
                    "USAGE_QUOTA_EXCEEDED",
                    "Daily transcript job quota exceeded.",
                )

    def record_job(self, user_id: str) -> None:
        key = (user_id, self._today())
        with self._lock:
            self._jobs[key] += 1

    def check_media_job_allowed(self, user_id: str) -> None:
        key = (user_id, self._today())
        with self._lock:
            if self._media_jobs[key] >= self._limits.daily_media_jobs:
                raise UsageQuotaExceeded(
                    "MEDIA_QUOTA_EXCEEDED",
                    "Daily authorized media job quota exceeded.",
                )

    def record_media_job(self, user_id: str) -> None:
        key = (user_id, self._today())
        with self._lock:
            self._media_jobs[key] += 1

    def reset(self) -> None:
        with self._lock:
            self._chat.clear()
            self._jobs.clear()
            self._media_jobs.clear()


# Module-level policy configured at app startup / tests.
_usage_policy = UsagePolicy(
    UsageLimits(daily_chat_messages=200, daily_transcript_jobs=100, daily_media_jobs=10)
)


def get_usage_policy() -> UsagePolicy:
    return _usage_policy


def configure_usage_policy(
    *,
    daily_chat_messages: int,
    daily_transcript_jobs: int,
    daily_media_jobs: int = 10,
) -> UsagePolicy:
    global _usage_policy
    _usage_policy = UsagePolicy(
        UsageLimits(
            daily_chat_messages=daily_chat_messages,
            daily_transcript_jobs=daily_transcript_jobs,
            daily_media_jobs=daily_media_jobs,
        )
    )
    return _usage_policy
