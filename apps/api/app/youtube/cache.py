"""In-process TTL cache for YouTube metadata (respect retention; no user-URL fetches)."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class _Entry[T]:
    value: T
    expires_at: float


class TtlCache[T]:
    def __init__(self, *, ttl_seconds: float, max_entries: int = 512) -> None:
        self._ttl = max(0.0, ttl_seconds)
        self._max = max(1, max_entries)
        self._store: dict[str, _Entry[T]] = {}

    def get(self, key: str) -> T | None:
        if self._ttl <= 0:
            return None
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() >= entry.expires_at:
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        if self._ttl <= 0:
            return
        if len(self._store) >= self._max and key not in self._store:
            # Drop an arbitrary expired or oldest-ish entry.
            oldest_key = next(iter(self._store))
            self._store.pop(oldest_key, None)
        self._store[key] = _Entry(value=value, expires_at=time.monotonic() + self._ttl)

    def clear(self) -> None:
        self._store.clear()
