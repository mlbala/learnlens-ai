"""Async engine / session factory for Neon (runtime) and SQLite (tests)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import Settings


def _to_async_url(url: str) -> str:
    """Normalize DATABASE_URL to an async SQLAlchemy URL."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url.removeprefix("sqlite://")
    return url


def create_engine(settings: Settings, *, url: str | None = None) -> AsyncEngine:
    """Create an async engine. Neon uses asyncpg; tests may pass sqlite URL."""
    database_url = url or settings.database_url
    if not database_url:
        msg = "DATABASE_URL is required for database access"
        raise RuntimeError(msg)
    async_url = _to_async_url(database_url)
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if async_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        # StaticPool keeps a single in-memory SQLite connection for the process/tests.
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        # Neon pooled connections: keep pool small; SSL handled by asyncpg DSN.
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 5
    return create_async_engine(async_url, **kwargs)


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
