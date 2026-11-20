"""Grounded chat thread APIs — evidence-validated answers with server citations."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from app.api.deps import CsrfAuth, CurrentAuth, DbSession, SettingsDep
from app.api.v1.schemas import (
    ChatMessageListResponse,
    ChatMessageOut,
    ChatThreadOut,
    CitationOut,
    CreateChatThreadRequest,
    PostChatMessageRequest,
    PostChatMessageResponse,
    QaAnalogyOut,
    QaClaimOut,
)
from app.core.errors import raise_api_error
from app.db.models.chat import ChatMessage, MessageCitation
from app.domain.qa_schemas import ExplanationMode
from app.services.grounded_qa import CitationOut as ServiceCitation
from app.services.grounded_qa import GroundedQaError, GroundedQaService

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _map_error(exc: GroundedQaError, request_id: str | None) -> None:
    raise_api_error(
        exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=request_id,
    )


def _citation_out(c: ServiceCitation) -> CitationOut:
    return CitationOut(
        citation_id=c.citation_id,
        video_id=c.video_id,
        video_title=c.video_title,
        segment_id=c.segment_id,
        snippet=c.snippet,
        start_ms=c.start_ms,
        end_ms=c.end_ms,
        youtube_url=c.youtube_url,
        timing_verified=c.timing_verified,
    )


def _message_out(
    message: ChatMessage,
    *,
    citations: list[CitationOut] | None = None,
    video_titles: dict[uuid.UUID, str] | None = None,
) -> ChatMessageOut:
    payload: dict[str, Any] = message.content_json if isinstance(message.content_json, dict) else {}
    claims = [
        QaClaimOut(
            text=str(c.get("text") or ""),
            citation_segment_ids=[str(x) for x in (c.get("citation_segment_ids") or [])],
        )
        for c in (payload.get("claims") or [])
        if isinstance(c, dict) and str(c.get("text") or "").strip()
    ]
    analogies = [
        QaAnalogyOut(
            text=str(a.get("text") or ""),
            origin=str(a.get("origin") or "ai_generated_illustration"),
        )
        for a in (payload.get("analogies") or [])
        if isinstance(a, dict) and str(a.get("text") or "").strip()
    ]
    return ChatMessageOut(
        id=message.id,
        thread_id=message.thread_id,
        workspace_id=message.workspace_id,
        role=message.role,
        content=message.content,
        explanation_mode=message.explanation_mode,
        confidence_label=message.confidence_label,
        unsupported=bool(message.unsupported),
        claims=claims,
        analogies=analogies,
        citations=citations or [],
        provider_run_id=message.provider_run_id,
        created_at=message.created_at,
    )


def _persisted_citations(
    rows: list[MessageCitation],
    *,
    video_titles: dict[uuid.UUID, str],
) -> list[CitationOut]:
    out: list[CitationOut] = []
    for row in rows:
        out.append(
            CitationOut(
                citation_id=row.citation_key,
                video_id=row.video_id,
                video_title=video_titles.get(row.video_id, ""),
                segment_id=row.segment_id,
                snippet=row.snippet,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                youtube_url=row.youtube_url,
                timing_verified=bool(row.timing_verified),
            )
        )
    return out


@router.post("/threads", response_model=ChatThreadOut)
async def create_thread(
    body: CreateChatThreadRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> ChatThreadOut:
    request_id = getattr(request.state, "request_id", None)
    if body.scope_kind in {"video", "playlist"} and body.scope_id is None:
        raise_api_error(
            422,
            code="SCOPE_ID_REQUIRED",
            message="scope_id is required for video and playlist threads.",
            request_id=request_id,
        )
    if body.scope_kind == "library" and body.scope_id is not None:
        raise_api_error(
            422,
            code="SCOPE_ID_NOT_ALLOWED",
            message="library scope must not include scope_id.",
            request_id=request_id,
        )
    service = GroundedQaService(db, settings)
    try:
        thread = await service.create_thread(
            workspace_id=ctx.workspace.id,
            created_by=ctx.user.id,
            scope_kind=body.scope_kind,  # type: ignore[arg-type]
            scope_id=body.scope_id,
            title=body.title,
        )
    except GroundedQaError as exc:
        _map_error(exc, request_id)
    return ChatThreadOut(
        id=thread.id,
        workspace_id=thread.workspace_id,
        scope_kind=thread.scope_kind,
        scope_id=thread.scope_id,
        title=thread.title,
        created_by=thread.created_by,
        created_at=thread.created_at,
    )


@router.post("/threads/{thread_id}/messages", response_model=PostChatMessageResponse)
async def post_message(
    thread_id: uuid.UUID,
    body: PostChatMessageRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> PostChatMessageResponse:
    request_id = getattr(request.state, "request_id", None)
    try:
        mode = ExplanationMode(body.explanation_mode)
    except ValueError:
        raise_api_error(
            422,
            code="INVALID_EXPLANATION_MODE",
            message="explanation_mode must be simple, standard, or technical.",
            request_id=request_id,
        )
    service = GroundedQaService(db, settings)
    try:
        result = await service.ask(
            thread_id=thread_id,
            workspace_id=ctx.workspace.id,
            question=body.question,
            explanation_mode=mode,
        )
    except GroundedQaError as exc:
        _map_error(exc, request_id)

    cites = [_citation_out(c) for c in result.citations]
    user_out = _message_out(result.user_message)
    assistant_out = _message_out(result.assistant_message, citations=cites)
    # Ensure claims/analogies from the validated turn are present even if content_json
    # was minimal (e.g. refusal path).
    if not assistant_out.claims and result.claims:
        assistant_out = assistant_out.model_copy(
            update={
                "claims": [
                    QaClaimOut(
                        text=c["text"],
                        citation_segment_ids=list(c["citation_segment_ids"]),
                    )
                    for c in result.claims
                ],
                "analogies": [
                    QaAnalogyOut(
                        text=a["text"],
                        origin=a.get("origin", "ai_generated_illustration"),
                    )
                    for a in result.analogies
                ],
            }
        )
    return PostChatMessageResponse(
        user_message=user_out,
        assistant_message=assistant_out,
        unsupported=result.unsupported,
        confidence_label=result.confidence_label,
        explanation_mode=result.explanation_mode.value,
    )


@router.get("/threads/{thread_id}/messages", response_model=ChatMessageListResponse)
async def list_messages(
    thread_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    limit: int = Query(default=50, ge=1, le=100),
    after: Annotated[uuid.UUID | None, Query()] = None,
) -> ChatMessageListResponse:
    request_id = getattr(request.state, "request_id", None)
    service = GroundedQaService(db, settings)
    try:
        messages, cites_by_msg = await service.list_messages(
            thread_id=thread_id,
            workspace_id=ctx.workspace.id,
            limit=limit,
            after_id=after,
        )
    except GroundedQaError as exc:
        _map_error(exc, request_id)

    video_ids = {c.video_id for rows in cites_by_msg.values() for c in rows}
    titles: dict[uuid.UUID, str] = {}
    if video_ids:
        from app.db.repositories import VideoRepository

        videos = VideoRepository(db)
        for vid in video_ids:
            row = await videos.get_in_workspace(video_id=vid, workspace_id=ctx.workspace.id)
            if row is not None:
                titles[vid] = row.title

    items = [
        _message_out(
            m,
            citations=_persisted_citations(cites_by_msg.get(m.id, []), video_titles=titles),
        )
        for m in messages
    ]
    return ChatMessageListResponse(items=items, limit=limit)
