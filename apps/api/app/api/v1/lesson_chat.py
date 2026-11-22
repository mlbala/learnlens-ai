"""Stored lesson chat: one thread per workspace and video, packed follow-ups."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import CsrfAuth, CurrentAuth, DbSession, SettingsDep
from app.api.v1.schemas import (
    ChatThreadOut,
    EvidencePassageOut,
    KeptEvidenceOut,
    LessonChatMessageListResponse,
    LessonChatMessageOut,
    LessonChatStateResponse,
    PostLessonChatRequest,
    PostLessonChatResponse,
    PrepareLessonChatRequest,
    PrepareLessonChatResponse,
    RetrieveLessonChatRequest,
    RetrieveLessonChatResponse,
)
from app.core.errors import raise_api_error
from app.db.models.chat import ChatMessage, ChatThread
from app.retrieval.session_lanes import SessionReranker
from app.services.session_chat import SessionChatError, SessionChatService, StoredTurn
from app.services.session_evidence import SearchHitInput

router = APIRouter(prefix="/api/v1/lesson-chat", tags=["lesson-chat"])


def _service(request: Request, db: DbSession, settings: SettingsDep) -> SessionChatService:
    reranker = getattr(request.app.state, "session_reranker", None)
    typed: SessionReranker | None = reranker if reranker is not None else None
    return SessionChatService(db, settings, reranker=typed)


def _fail(exc: SessionChatError, request_id: str | None) -> None:
    raise_api_error(exc.status_code, code=exc.code, message=exc.message, request_id=request_id)


def _thread_out(thread: ChatThread) -> ChatThreadOut:
    return ChatThreadOut(
        id=thread.id,
        workspace_id=thread.workspace_id,
        scope_kind=thread.scope_kind,
        scope_id=thread.scope_id,
        title=thread.title,
        created_by=thread.created_by,
        created_at=thread.created_at,
    )


def _message_out(message: ChatMessage) -> LessonChatMessageOut:
    payload = message.content_json if isinstance(message.content_json, dict) else None
    return LessonChatMessageOut(
        id=message.id,
        thread_id=message.thread_id,
        workspace_id=message.workspace_id,
        role=message.role,
        content=message.content,
        explanation_mode=message.explanation_mode,
        external_search_enabled=message.external_search_enabled,
        content_json=payload,
        confidence_label=message.confidence_label,
        unsupported=bool(message.unsupported),
        created_at=message.created_at,
    )


def _stored(result: StoredTurn) -> PostLessonChatResponse:
    return PostLessonChatResponse(
        thread=_thread_out(result.thread),
        user_message=_message_out(result.user_message),
        assistant_message=_message_out(result.assistant_message),
        segment_ids=result.segment_ids,
    )


def _answer_payload(body: PostLessonChatRequest) -> dict | None:
    if body.answer is None:
        return None
    return body.answer.model_dump()


@router.get("/videos/{video_id}", response_model=LessonChatStateResponse)
async def read_lesson_chat(
    video_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
) -> LessonChatStateResponse:
    request_id = getattr(request.state, "request_id", None)
    service = _service(request, db, settings)
    try:
        thread = await service.thread_for_video(workspace_id=ctx.workspace.id, video_id=video_id)
        _thread, _packed, segment_ids = await service.prepare(
            workspace_id=ctx.workspace.id,
            video_id=video_id,
            external_search=False,
        )
        messages: list[ChatMessage] = []
        if thread is not None:
            messages = await service.list_messages(
                thread_id=thread.id,
                workspace_id=ctx.workspace.id,
            )
    except SessionChatError as exc:
        _fail(exc, request_id)
    return LessonChatStateResponse(
        thread=_thread_out(thread) if thread is not None else None,
        messages=[_message_out(row) for row in messages],
        segment_ids=segment_ids,
    )


@router.post("/videos/{video_id}/prepare", response_model=PrepareLessonChatResponse)
async def prepare_lesson_chat(
    video_id: uuid.UUID,
    body: PrepareLessonChatRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> PrepareLessonChatResponse:
    request_id = getattr(request.state, "request_id", None)
    service = _service(request, db, settings)
    try:
        thread, packed, segment_ids = await service.prepare(
            workspace_id=ctx.workspace.id,
            video_id=video_id,
            external_search=body.external_search,
        )
    except SessionChatError as exc:
        _fail(exc, request_id)
    return PrepareLessonChatResponse(
        thread_id=thread.id if thread is not None else None,
        packed_history=packed,
        segment_ids=segment_ids,
    )


@router.post("/videos/{video_id}/retrieve", response_model=RetrieveLessonChatResponse)
async def retrieve_lesson_evidence(
    video_id: uuid.UUID,
    body: RetrieveLessonChatRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> RetrieveLessonChatResponse:
    request_id = getattr(request.state, "request_id", None)
    service = _service(request, db, settings)
    hits = [
        SearchHitInput(
            title=source.title,
            url=source.url,
            snippet=source.snippet,
            provider=source.provider,
        )
        for source in body.sources
    ]
    try:
        thread, packet = await service.retrieve(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            video_id=video_id,
            question=body.question,
            external_search=body.external_search,
            sources=hits if body.external_search else [],
        )
    except SessionChatError as exc:
        _fail(exc, request_id)
    passages = [
        EvidencePassageOut(
            id=uuid.UUID(row["id"]),
            evidence_origin=row["evidence_origin"],
            evidence_provider=row["evidence_provider"],
            text=row["text"],
            title=row["title"],
            source_url=row["source_url"],
        )
        for row in packet.public_passages()
    ]
    kept = [
        KeptEvidenceOut(id=uuid.UUID(row["id"]), evidence_origin=row["evidence_origin"])
        for row in packet.kept
    ]
    return RetrieveLessonChatResponse(
        thread_id=thread.id,
        decision=packet.decision,
        video_covered=packet.video_covered,
        passages=passages,
        kept=kept,
    )


@router.post("/videos/{video_id}/messages", response_model=PostLessonChatResponse)
async def post_lesson_chat_message(
    video_id: uuid.UUID,
    body: PostLessonChatRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> PostLessonChatResponse:
    request_id = getattr(request.state, "request_id", None)
    service = _service(request, db, settings)
    try:
        result = await service.post_message(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            video_id=video_id,
            question=body.question,
            explanation_mode=body.explanation_mode,
            external_search=body.external_search,
            answer=_answer_payload(body),
        )
    except SessionChatError as exc:
        _fail(exc, request_id)
    return _stored(result)


@router.get("/threads/{thread_id}/messages", response_model=LessonChatMessageListResponse)
async def list_lesson_chat_messages(
    thread_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
) -> LessonChatMessageListResponse:
    request_id = getattr(request.state, "request_id", None)
    service = _service(request, db, settings)
    try:
        messages = await service.list_messages(thread_id=thread_id, workspace_id=ctx.workspace.id)
    except SessionChatError as exc:
        _fail(exc, request_id)
    return LessonChatMessageListResponse(items=[_message_out(row) for row in messages])


@router.post("/threads/{thread_id}/messages", response_model=PostLessonChatResponse)
async def post_lesson_chat_on_thread(
    thread_id: uuid.UUID,
    body: PostLessonChatRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> PostLessonChatResponse:
    request_id = getattr(request.state, "request_id", None)
    service = _service(request, db, settings)
    try:
        thread = await service.get_thread(thread_id=thread_id, workspace_id=ctx.workspace.id)
        if thread is None or thread.scope_kind != "video" or thread.scope_id is None:
            raise SessionChatError(404, "NOT_FOUND", "Resource not found.")
        result = await service.post_message(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            video_id=thread.scope_id,
            question=body.question,
            explanation_mode=body.explanation_mode,
            external_search=body.external_search,
            answer=_answer_payload(body),
        )
    except SessionChatError as exc:
        _fail(exc, request_id)
    return _stored(result)
