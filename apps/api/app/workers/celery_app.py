"""Celery application — Redis broker in prod; eager/memory for offline tests."""

from __future__ import annotations

import os

from celery import Celery

from app.core.settings import get_settings


def _build_celery() -> Celery:
    settings = get_settings()
    eager = settings.celery_task_always_eager
    broker = settings.redis_url if not eager else "memory://"
    backend = settings.redis_url if not eager else "cache+memory://"

    app = Celery("learnlens", broker=broker, backend=backend)
    app.conf.update(
        task_always_eager=eager,
        task_eager_propagates=True,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        # Bound worker concurrency / time limits (no open-ended agent loops).
        task_soft_time_limit=settings.transcript_job_soft_time_limit_seconds,
        task_time_limit=settings.transcript_job_time_limit_seconds,
        worker_prefetch_multiplier=1,
        imports=("app.workers.tasks",),
    )
    # Allow env override without re-reading Settings (tests set env before import).
    if os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() in {"1", "true", "yes"}:
        app.conf.task_always_eager = True
        app.conf.task_eager_propagates = True
    return app


celery_app = _build_celery()


def is_eager() -> bool:
    return bool(celery_app.conf.task_always_eager)
