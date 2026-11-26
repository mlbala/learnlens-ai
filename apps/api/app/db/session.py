"""Async engine / session factory for Neon (runtime) and SQLite (tests)."""

from __future__ import annotations

import ssl
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import event
from sqlalchemy.exc import DisconnectionError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import Settings


def _to_async_url(url: str) -> str:
    """Normalize DATABASE_URL to an async SQLAlchemy URL.

    Neon libpq URLs include sslmode and channel_binding. asyncpg.connect does not
    accept those names, so they are removed here and SSL is passed via connect_args.
    """
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    elif url.startswith("sqlite://") and not url.startswith("sqlite+"):
        url = "sqlite+aiosqlite://" + url.removeprefix("sqlite://")
    if not url.startswith("postgresql"):
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.pop("channel_binding", None)
    query.pop("sslmode", None)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _asyncpg_ssl_context(url: str) -> ssl.SSLContext | None:
    """SSL context for Neon. Matches the readiness probe (encrypt, do not pin hostname)."""
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    sslmode = (query.get("sslmode") or "").lower()
    host = (parsed.hostname or "").lower()
    needs_ssl = sslmode in {"require", "verify-ca", "verify-full"} or host.endswith("neon.tech")
    if not needs_ssl:
        return None
    ctx = ssl.create_default_context()
    if sslmode in {"", "require", "prefer"} or host.endswith("neon.tech"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def create_engine(settings: Settings, *, url: str | None = None) -> AsyncEngine:
    """Create an async engine. Neon uses asyncpg; tests may pass sqlite URL."""
    database_url = url or settings.database_url
    if not database_url:
        msg = "DATABASE_URL is required for database access"
        raise RuntimeError(msg)
    async_url = _to_async_url(database_url)
    kwargs: dict[str, Any] = {}
    if async_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        # StaticPool keeps a single in-memory SQLite connection for the process/tests.
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        # Neon pooled connections: keep the pool small. SSL is a connect arg, not a URL param.
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 5
        ssl_ctx = _asyncpg_ssl_context(database_url)
        if ssl_ctx is not None:
            kwargs["connect_args"] = {"ssl": ssl_ctx}
    engine = create_async_engine(async_url, **kwargs)
    if not async_url.startswith("sqlite"):
        install_idle_ping(engine)
    return engine


# A pooled connection idle this long may have been closed while Neon paused, so it is
# pinged before use. A connection used more recently is not: each ping is a round trip.
IDLE_PING_SECONDS = 60.0
_IDLE_SINCE = "learnlens_idle_since"


def install_idle_ping(engine: AsyncEngine, *, clock: Any = time.monotonic) -> None:
    """Ping only connections that sat idle in the pool; replace one that fails."""
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "checkin")
    def _checkin(dbapi_connection: Any, record: Any) -> None:
        if record is not None:
            record.info[_IDLE_SINCE] = clock()

    @event.listens_for(sync_engine, "checkout")
    def _checkout(dbapi_connection: Any, record: Any, proxy: Any) -> None:
        since = record.info.get(_IDLE_SINCE)
        if since is None or clock() - since < IDLE_PING_SECONDS:
            return
        try:
            sync_engine.dialect.do_ping(dbapi_connection)
        except Exception as exc:
            # The pool drops this connection and opens a new one.
            raise DisconnectionError("Idle database connection was closed.") from exc


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
