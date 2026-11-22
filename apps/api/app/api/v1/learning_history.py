"""Signed-in workspace lesson history. Neon rows only — no media download."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request

from app.api.deps import CsrfAuth, CurrentAuth, DbSession
from app.api.v1.schemas import (
    LearningHistorySettingsOut,
    LearningHistorySettingsUpdate,
    LessonDetailOut,
    LessonListResponse,
    LessonSegmentOut,
    LessonSummaryOut,
    SaveLessonRequest,
    VideoOut,
)
from app.core.errors import raise_api_error
from app.db.models import TranscriptSegment, Video
from app.services.lesson_history import (
    SOURCE_KIND_GEMINI_YOUTUBE,
    LessonHistoryError,
    LessonHistoryService,
)

router = APIRouter(prefix="/api/v1/learning-history", tags=["learning-history"])
settings_router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def _lesson_meta(video: Video) -> tuple[str, list[str]]:
    meta: dict[str, Any] = video.metadata_json if isinstance(video.metadata_json, dict) else {}
    lesson = meta.get("gemini_lesson") if isinstance(meta.get("gemini_lesson"), dict) else {}
    summary = str(lesson.get("summary") or "")
    raw_points = lesson.get("key_points") if isinstance(lesson.get("key_points"), list) else []
    points = [str(point) for point in raw_points if str(point).strip()]
    return summary, points


def _segment_out(row: TranscriptSegment) -> LessonSegmentOut:
    return LessonSegmentOut(
        id=row.id,
        ordinal=row.ordinal,
        text=row.text,
        content_hash=row.content_hash,
        start_ms=row.start_ms,
        end_ms=row.end_ms,
        evidence_origin=row.evidence_origin or "",
        evidence_provider=row.evidence_provider or "",
        source_kind=SOURCE_KIND_GEMINI_YOUTUBE,
    )


def _video_out(video: Video) -> VideoOut:
    return VideoOut(
        id=video.id,
        workspace_id=video.workspace_id,
        youtube_video_id=video.youtube_video_id,
        title=video.title,
        status=video.status,
        channel_title=video.channel_title,
        duration_seconds=video.duration_seconds,
        source_url=video.source_url,
        metadata_json=video.metadata_json,
        transcript_access=True,
        coverage="ready",
    )


def _detail(
    video: Video,
    segments: list[TranscriptSegment],
    *,
    created: bool = False,
) -> LessonDetailOut:
    summary, points = _lesson_meta(video)
    return LessonDetailOut(
        video=_video_out(video),
        last_opened_at=video.last_opened_at,
        summary=summary,
        key_points=points,
        source_kind=SOURCE_KIND_GEMINI_YOUTUBE,
        created=created,
        segments=[_segment_out(row) for row in segments],
    )


def _summary(video: Video, segments: list[TranscriptSegment]) -> LessonSummaryOut:
    summary, points = _lesson_meta(video)
    return LessonSummaryOut(
        id=video.id,
        workspace_id=video.workspace_id,
        youtube_video_id=video.youtube_video_id,
        title=video.title,
        status=video.status,
        channel_title=video.channel_title,
        duration_seconds=video.duration_seconds,
        source_url=video.source_url,
        last_opened_at=video.last_opened_at,
        summary=summary,
        key_points=points,
        transcript_access=True,
        segment_ids=[row.id for row in segments],
    )


def _fail(exc: LessonHistoryError, request_id: str | None) -> None:
    raise_api_error(exc.status_code, code=exc.code, message=exc.message, request_id=request_id)


@router.get("", response_model=LessonListResponse)
async def list_learning_history(ctx: CurrentAuth, db: DbSession) -> LessonListResponse:
    service = LessonHistoryService(db)
    videos = await service.list_lessons(ctx.workspace.id)
    items: list[LessonSummaryOut] = []
    for video in videos:
        _video, segments = await service.get_lesson(
            workspace_id=ctx.workspace.id,
            video_id=video.id,
        )
        items.append(_summary(video, segments))
    limit = await service.get_limit(ctx.workspace.id)
    return LessonListResponse(items=items, learning_history_limit=limit)


@router.post("", response_model=LessonDetailOut)
async def save_learning_history(
    body: SaveLessonRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
) -> LessonDetailOut:
    request_id = getattr(request.state, "request_id", None)
    service = LessonHistoryService(db)
    try:
        video, segments, created = await service.save_lesson(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            youtube_video_id=body.youtube_video_id,
            title=body.title,
            channel_title=body.channel_title,
            summary=body.summary,
            key_points=body.key_points,
            transcript=body.transcript,
            source_url=body.source_url,
        )
    except LessonHistoryError as exc:
        _fail(exc, request_id)
    return _detail(video, segments, created=created)


@router.get("/{video_id}", response_model=LessonDetailOut)
async def get_learning_history_lesson(
    video_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
) -> LessonDetailOut:
    request_id = getattr(request.state, "request_id", None)
    service = LessonHistoryService(db)
    try:
        video, segments = await service.get_lesson(
            workspace_id=ctx.workspace.id,
            video_id=video_id,
        )
    except LessonHistoryError as exc:
        _fail(exc, request_id)
    return _detail(video, segments)


@router.post("/{video_id}/open", response_model=LessonDetailOut)
async def open_learning_history_lesson(
    video_id: uuid.UUID,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
) -> LessonDetailOut:
    request_id = getattr(request.state, "request_id", None)
    service = LessonHistoryService(db)
    try:
        video, segments = await service.open_lesson(
            workspace_id=ctx.workspace.id,
            video_id=video_id,
        )
    except LessonHistoryError as exc:
        _fail(exc, request_id)
    return _detail(video, segments)


@settings_router.get("/learning-history", response_model=LearningHistorySettingsOut)
async def get_learning_history_settings(
    ctx: CurrentAuth,
    db: DbSession,
) -> LearningHistorySettingsOut:
    service = LessonHistoryService(db)
    limit = await service.get_limit(ctx.workspace.id)
    return LearningHistorySettingsOut(learning_history_limit=limit)


@settings_router.put("/learning-history", response_model=LearningHistorySettingsOut)
async def put_learning_history_settings(
    body: LearningHistorySettingsUpdate,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
) -> LearningHistorySettingsOut:
    request_id = getattr(request.state, "request_id", None)
    service = LessonHistoryService(db)
    try:
        limit = await service.set_limit(ctx.workspace.id, body.learning_history_limit)
    except LessonHistoryError as exc:
        _fail(exc, request_id)
    return LearningHistorySettingsOut(learning_history_limit=limit)
