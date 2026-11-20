"""Celery tasks for transcript ingestion and playlist synthesis jobs."""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.core.observability.metrics import get_worker_metrics
from app.core.observability.tracing import (
    bind_from_celery_headers,
    clear_context,
    start_span,
)
from app.core.settings import clear_settings_cache, get_settings
from app.db.session import create_engine, create_session_factory
from app.services.playlist_synthesis import PlaylistSynthesisService
from app.services.transcript_ingest import TranscriptIngestService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _process_job_async(job_id: uuid.UUID) -> str:
    clear_settings_cache()
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            service = TranscriptIngestService(session, settings)
            # Bounded retry loop inside the task (no unbounded Celery recursion).
            max_attempts = settings.transcript_job_max_attempts
            final_status = "unknown"
            for _ in range(max_attempts):
                job = await service.process_job(job_id)
                final_status = job.status
                if job.status in {"succeeded", "failed"}:
                    break
                # queued again after retryable failure — continue loop
            await session.commit()
            return final_status
    finally:
        await engine.dispose()


async def _process_playlist_synthesis_async(job_id: uuid.UUID) -> str:
    clear_settings_cache()
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            from app.db.repositories import IngestionJobRepository

            service = PlaylistSynthesisService(session, settings)
            await service.process_job(job_id)
            job = await IngestionJobRepository(session).get_by_id(job_id)
            await session.commit()
            return job.status if job else "unknown"
    finally:
        await engine.dispose()


def _task_headers(task) -> dict:
    headers = getattr(task.request, "headers", None) or {}
    return dict(headers) if headers else {}


@celery_app.task(
    name="app.workers.tasks.process_transcript_job",
    bind=True,
    max_retries=0,  # retries are bounded inside process_job / loop above
)
def process_transcript_job(self, job_id: str) -> dict[str, str]:
    """Process a transcript ingestion job. Never logs raw transcript content."""
    bind_from_celery_headers(_task_headers(self))
    metrics = get_worker_metrics()
    metrics.record_start("transcript")
    try:
        with start_span("celery.process_transcript_job", job_id=job_id):
            logger.info("transcript_job_start", extra={"job_id": job_id})
            status = asyncio.run(_process_job_async(uuid.UUID(job_id)))
            logger.info(
                "transcript_job_finish",
                extra={"job_id": job_id, "status": status},
            )
            if status == "succeeded":
                metrics.record_success("transcript")
            elif status == "failed":
                metrics.record_failure("transcript")
            return {"job_id": job_id, "status": status}
    finally:
        clear_context()


@celery_app.task(
    name="app.workers.tasks.process_playlist_synthesis_job",
    bind=True,
    max_retries=0,
)
def process_playlist_synthesis_job(self, job_id: str) -> dict[str, str]:
    """Process playlist course synthesis. Never logs raw transcript content."""
    bind_from_celery_headers(_task_headers(self))
    metrics = get_worker_metrics()
    metrics.record_start("playlist_synthesis")
    try:
        with start_span("celery.process_playlist_synthesis_job", job_id=job_id):
            logger.info("playlist_synthesis_job_start", extra={"job_id": job_id})
            status = asyncio.run(_process_playlist_synthesis_async(uuid.UUID(job_id)))
            logger.info(
                "playlist_synthesis_job_finish",
                extra={"job_id": job_id, "status": status},
            )
            if status == "succeeded":
                metrics.record_success("playlist_synthesis")
            elif status == "failed":
                metrics.record_failure("playlist_synthesis")
            return {"job_id": job_id, "status": status}
    finally:
        clear_context()
