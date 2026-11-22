"""Alembic environment — targets Neon via DATABASE_URL_UNPOOLED (or DATABASE_URL)."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from app.db.base import Base
from app.db.models import (  # noqa: F401 — register metadata
    Chapter,
    ExternalEvidence,
    IngestionJob,
    OutboxEvent,
    Playlist,
    PlaylistItem,
    Session,
    SourceAsset,
    TranscriptSegment,
    User,
    Video,
    Workspace,
    WorkspaceMembership,
)
from app.db.session import _asyncpg_ssl_context, _to_async_url
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _raw_database_url() -> str:
    """Prefer unpooled Neon URL for DDL; never log the value."""
    return (
        os.environ.get("DATABASE_URL_UNPOOLED", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
        or config.get_main_option("sqlalchemy.url")
        or ""
    )


def _database_url() -> str:
    return _to_async_url(_raw_database_url())


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    conf = config.get_section(config.config_ini_section) or {}
    raw_url = _raw_database_url()
    conf["sqlalchemy.url"] = _to_async_url(raw_url)
    ssl_ctx = _asyncpg_ssl_context(raw_url)
    connectable = async_engine_from_config(
        conf,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"ssl": ssl_ctx} if ssl_ctx is not None else {},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
