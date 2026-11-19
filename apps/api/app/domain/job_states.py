"""Bounded ingestion job state machine — consistent transitions only."""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobStage(StrEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    PERSISTING = "persisting"
    SEGMENTING = "segmenting"
    COMPLETE = "complete"
    ERROR = "error"


# Allowed (status, stage) pairs and forward edges.
_RETRY = (JobStatus.QUEUED, JobStage.PENDING)
_FAIL = (JobStatus.FAILED, JobStage.ERROR)

_TRANSITIONS: dict[tuple[str, str], set[tuple[str, str]]] = {
    (JobStatus.QUEUED, JobStage.PENDING): {
        (JobStatus.RUNNING, JobStage.VALIDATING),
        _FAIL,
    },
    (JobStatus.RUNNING, JobStage.VALIDATING): {
        (JobStatus.RUNNING, JobStage.PERSISTING),
        _FAIL,
        _RETRY,  # bounded worker retry
    },
    (JobStatus.RUNNING, JobStage.PERSISTING): {
        (JobStatus.RUNNING, JobStage.SEGMENTING),
        _FAIL,
        _RETRY,
    },
    (JobStatus.RUNNING, JobStage.SEGMENTING): {
        (JobStatus.SUCCEEDED, JobStage.COMPLETE),
        _FAIL,
        _RETRY,
    },
    (JobStatus.FAILED, JobStage.ERROR): set(),
    (JobStatus.SUCCEEDED, JobStage.COMPLETE): set(),
}


def can_transition(
    *,
    from_status: str,
    from_stage: str,
    to_status: str,
    to_stage: str,
) -> bool:
    allowed = _TRANSITIONS.get((from_status, from_stage))
    if allowed is None:
        return False
    return (to_status, to_stage) in allowed


def stage_percent(status: str, stage: str) -> int:
    if status == JobStatus.SUCCEEDED:
        return 100
    if status == JobStatus.FAILED:
        return 100
    mapping = {
        JobStage.PENDING: 0,
        JobStage.VALIDATING: 20,
        JobStage.PERSISTING: 45,
        JobStage.SEGMENTING: 75,
        JobStage.COMPLETE: 100,
        JobStage.ERROR: 100,
    }
    return mapping.get(stage, 0)
