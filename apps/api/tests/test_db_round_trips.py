"""Fewer database round trips: idle-only pings and a throttled last-seen write."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
from app.db.repositories.sessions import SEEN_REFRESH_SECONDS, SessionRepository
from app.db.session import IDLE_PING_SECONDS, install_idle_ping
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_only_idle_connections_are_pinged(tmp_path: Path) -> None:
    async def run() -> tuple[int, int, int]:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ping.db'}")
        clock = Clock()
        install_idle_ping(engine, clock=clock)
        pings: list[int] = []
        dialect = engine.sync_engine.dialect
        original = dialect.do_ping

        def counting_ping(dbapi_connection: Any) -> bool:
            pings.append(1)
            return original(dbapi_connection)

        dialect.do_ping = counting_ping  # type: ignore[method-assign]
        async with engine.connect() as conn:  # new connection: no ping
            await conn.execute(text("select 1"))
        first = len(pings)
        clock.now += IDLE_PING_SECONDS / 2
        async with engine.connect() as conn:  # recently used: no ping
            await conn.execute(text("select 1"))
        recent = len(pings)
        clock.now += IDLE_PING_SECONDS + 1
        async with engine.connect() as conn:  # idle: pinged once
            await conn.execute(text("select 1"))
        await engine.dispose()
        return first, recent, len(pings)

    assert anyio.run(run) == (0, 0, 1)


def test_a_dead_idle_connection_is_replaced(tmp_path: Path) -> None:
    async def run() -> int:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'dead.db'}")
        clock = Clock()
        install_idle_ping(engine, clock=clock)
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        failed: list[int] = []
        dialect = engine.sync_engine.dialect
        original = dialect.do_ping

        def failing_once(dbapi_connection: Any) -> bool:
            if not failed:
                failed.append(1)
                raise ConnectionError("closed while idle")
            return original(dbapi_connection)

        dialect.do_ping = failing_once  # type: ignore[method-assign]
        clock.now += IDLE_PING_SECONDS + 1
        async with engine.connect() as conn:
            value = (await conn.execute(text("select 1"))).scalar_one()
        await engine.dispose()
        return int(value)

    assert anyio.run(run) == 1


class FlushCounter:
    def __init__(self) -> None:
        self.flushes = 0

    async def flush(self) -> None:
        self.flushes += 1


def test_last_seen_is_written_once_per_window() -> None:
    db = FlushCounter()
    repo = SessionRepository(db)  # type: ignore[arg-type]
    recent = SimpleNamespace(last_seen_at=datetime.now(UTC) - timedelta(seconds=5))
    stale = SimpleNamespace(
        last_seen_at=datetime.now(UTC) - timedelta(seconds=SEEN_REFRESH_SECONDS + 1)
    )
    never = SimpleNamespace(last_seen_at=None)

    anyio.run(repo.touch, recent)
    assert db.flushes == 0
    anyio.run(repo.touch, stale)
    anyio.run(repo.touch, never)
    assert db.flushes == 2
    assert never.last_seen_at is not None
