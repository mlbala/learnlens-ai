"""Per-request database counts: how many queries ran and how long they took.

Each query is a network round trip to Neon, so the count explains most of a slow
request. Only counts and milliseconds are kept; SQL text and parameters are not.
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(slots=True)
class DbStats:
    queries: int = 0
    seconds: float = 0.0

    @property
    def milliseconds(self) -> int:
        return round(self.seconds * 1000)


_CURRENT: ContextVar[DbStats | None] = ContextVar("learnlens_db_stats", default=None)
_STARTED = "_learnlens_query_started"


def start_request_stats() -> DbStats:
    """Begin counting for the current request. Child tasks share the same counter."""
    stats = DbStats()
    _CURRENT.set(stats)
    return stats


def current_stats() -> DbStats | None:
    return _CURRENT.get()


def install_db_stats(engine: AsyncEngine) -> None:
    """Count every statement the engine sends. Safe to call once per engine."""
    sync_engine = engine.sync_engine
    if getattr(sync_engine, "_learnlens_db_stats", False):
        return
    sync_engine._learnlens_db_stats = True  # type: ignore[attr-defined]

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(
        conn: Any, cursor: Any, statement: Any, params: Any, context: Any, many: Any
    ) -> None:
        if context is not None:
            setattr(context, _STARTED, time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(
        conn: Any, cursor: Any, statement: Any, params: Any, context: Any, many: Any
    ) -> None:
        stats = _CURRENT.get()
        if stats is None:
            return
        stats.queries += 1
        started = getattr(context, _STARTED, None) if context is not None else None
        if started is not None:
            stats.seconds += time.perf_counter() - started
