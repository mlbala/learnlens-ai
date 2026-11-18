"""In-process sliding-window rate limiter for auth endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """Fail-closed when a key exceeds `limit` events inside `window_seconds`."""

    def __init__(self, *, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


# Module-level limiter configured at app startup / tests.
auth_rate_limiter = SlidingWindowRateLimiter(limit=20, window_seconds=60.0)


def configure_auth_rate_limiter(*, limit: int, window_seconds: float) -> None:
    global auth_rate_limiter
    auth_rate_limiter = SlidingWindowRateLimiter(limit=limit, window_seconds=window_seconds)
