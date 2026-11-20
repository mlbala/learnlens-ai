"""Connectivity probes for Neon Postgres and Qdrant Cloud (no AI providers)."""

from __future__ import annotations

import logging
import ssl
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import asyncpg
from qdrant_client import QdrantClient

from app.core.settings import Settings

logger = logging.getLogger("learnlens.health")


def _asyncpg_connect_args(database_url: str) -> tuple[str, ssl.SSLContext | None]:
    """Adapt a Neon/libpq URL for asyncpg (sslmode query params are not portable)."""
    parsed = urlparse(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    sslmode = (query.pop("sslmode", None) or "").lower()
    query.pop("channel_binding", None)
    cleaned = urlunparse(parsed._replace(query=urlencode(query)))

    host = (parsed.hostname or "").lower()
    needs_ssl = sslmode in {"require", "verify-ca", "verify-full"} or host.endswith("neon.tech")
    if not needs_ssl:
        return cleaned, None

    ctx = ssl.create_default_context()
    # Neon pooled endpoints present a cert that verify-full may reject locally;
    # require encryption without pinning hostname for the readiness probe.
    if sslmode in {"", "require", "prefer"} or host.endswith("neon.tech"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return cleaned, ctx


async def check_neon(settings: Settings) -> dict[str, Any]:
    """Verify Neon accepts a simple query. Does not create schema or migrate."""
    if not settings.database_url:
        return {"ok": False, "error": "DATABASE_URL not configured"}
    try:
        dsn, ssl_ctx = _asyncpg_connect_args(settings.database_url)
        conn = await asyncpg.connect(dsn, timeout=5, ssl=ssl_ctx)
        try:
            value = await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
        if value != 1:
            return {"ok": False, "error": "unexpected SELECT 1 result"}
        return {"ok": True}
    except Exception as exc:
        logger.warning("neon_probe_failed", extra={"error_type": type(exc).__name__})
        return {"ok": False, "error": type(exc).__name__}


def check_qdrant(settings: Settings) -> dict[str, Any]:
    """Verify Qdrant Cloud responds (list collections). No index mutations."""
    if not settings.qdrant_url:
        return {"ok": False, "error": "QDRANT_URL not configured"}
    if not settings.qdrant_api_key:
        return {"ok": False, "error": "QDRANT_API_KEY not configured"}
    try:
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=5,
            check_compatibility=False,
        )
        client.get_collections()
        return {"ok": True}
    except Exception as exc:
        logger.warning("qdrant_probe_failed", extra={"error_type": type(exc).__name__})
        return {"ok": False, "error": type(exc).__name__}


def check_redis(settings: Settings) -> dict[str, Any]:
    """
    Probe Redis broker connectivity when workers are not eager.

    Uses a lightweight TCP/socket check via redis URL parsing — no paid APIs.
    When CELERY_TASK_ALWAYS_EAGER is true, reports skipped/ok for local offline mode.
    """
    if settings.celery_task_always_eager:
        return {"ok": True, "skipped": True, "reason": "celery_eager"}
    url = (settings.redis_url or "").strip()
    if not url:
        return {"ok": False, "error": "REDIS_URL not configured"}
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        import socket

        with socket.create_connection((host, port), timeout=2.0):
            return {"ok": True}
    except Exception as exc:
        logger.warning("redis_probe_failed", extra={"error_type": type(exc).__name__})
        return {"ok": False, "error": type(exc).__name__}
