"""Celery tasks for transcript ingestion jobs."""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.core.settings import clear_settings_cache, get_settings
from app.db.session import create_engine, create_session_factory
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


@celery_app.task(
    name="app.workers.tasks.process_transcript_job",
    bind=True,
    max_retries=0,  # retries are bounded inside process_job / loop above
)
def process_transcript_job(self, job_id: str) -> dict[str, str]:  # noqa: ARG001
    """Process a transcript ingestion job. Never logs raw transcript content."""
    logger.info("transcript_job_start", extra={"job_id": job_id})
    status = asyncio.run(_process_job_async(uuid.UUID(job_id)))
    logger.info(
        "transcript_job_finish",
        extra={"job_id": job_id, "status": status},
    )
    return {"job_id": job_id, "status": status}
