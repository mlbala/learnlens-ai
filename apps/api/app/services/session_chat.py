"""One stored chat thread per workspace and lesson video.

Neon holds the turns and outside-search rows. Qdrant holds derived points for
the video lane and the external lane. Full passage text stays in Neon.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ModelRequest, TextModel
from app.ai.factory import build_text_model
from app.core.settings import Settings
from app.db.models import ExternalEvidence, TranscriptSegment, Video
from app.db.models.chat import ChatMessage, ChatThread
from app.db.repositories.chat import ChatMessageRepository, ChatThreadRepository
from app.retrieval.session_lanes import ABSTAIN_BODY, ABSTAIN_HEADING, SessionReranker
from app.services.session_evidence import EvidencePacket, SearchHitInput, SessionEvidenceService
from app.services.session_review import (
    ModelSessionReviewer,
    ReviewRequest,
    ReviewUnavailable,
    ReviewVerdict,
    SessionReviewer,
    build_review_request,
    deterministic_reasons,
    is_retired_chat_model,
    is_review_timeout,
    merge_verdict,
    rejection_note,
    withheld_answer,
)

logger = logging.getLogger(__name__)

HISTORY_TURN_LIMIT = 8
SOURCE_PROVIDERS = frozenset({"tavily", "semantic_scholar", "openalex"})
FOLLOWUP_RULE = (
    'Pronouns and short follow-ups such as "explain that", "give an example", and "why" '
    "refer to the previous lesson panel. They do not refer to an earlier paper summary."
)
_SECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["heading", "body"],
    "properties": {"heading": {"type": "string"}, "body": {"type": "string"}},
}
LESSON_FOLLOWUP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["lesson", "external"],
    "properties": {
        "lesson": {"type": "array", "items": _SECTION_SCHEMA},
        "external": {"type": "array", "items": _SECTION_SCHEMA},
    },
}


class SessionChatError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FollowupSection:
    heading: str
    body: str


@dataclass(frozen=True)
class FollowupSource:
    provider: str
    title: str
    url: str


@dataclass(frozen=True)
class FollowupTurn:
    question: str
    lesson: tuple[FollowupSection, ...]
    external: tuple[FollowupSection, ...]
    sources: tuple[FollowupSource, ...]


@dataclass(frozen=True)
class StoredTurn:
    thread: ChatThread
    user_message: ChatMessage
    assistant_message: ChatMessage
    segment_ids: list[uuid.UUID]


def pack_followup(turns: list[FollowupTurn], *, external_search: bool) -> str:
    """Last 8 turns. Checkbox off keeps lesson panels and drops outside text."""
    window = turns[-HISTORY_TURN_LIMIT:]
    if not window:
        return ""
    if external_search:
        header = (
            "Earlier turns in this lesson thread. "
            "Each lesson block is video_transcript and is the video. "
            "Each outside block is external_search and is not the video. " + FOLLOWUP_RULE
        )
    else:
        header = (
            "Earlier turns in this lesson thread. "
            "Only user questions and lesson panels are included. "
            "Earlier outside-search text is omitted. " + FOLLOWUP_RULE
        )
    lines = [header, ""]
    for number, turn in enumerate(window, start=1):
        lines.append(f"Turn {number}")
        lines.append("User question:")
        lines.append(turn.question.strip())
        lines.append("Lesson panel (video_transcript):")
        lines.append(_section_text(turn.lesson) or "(no lesson panel)")
        if external_search:
            lines.append("Outside panel (external_search):")
            lines.append(_section_text(turn.external) or "(none)")
            lines.append("Outside sources (external_search):")
            lines.append(_source_text(turn.sources) or "(none)")
        lines.append("")
    return "\n".join(lines).strip()


def model_user_input(
    *,
    packed_history: str,
    question: str,
    external_search: bool,
    evidence_block: str = "",
) -> str:
    """Prompt for the new question plus the packed history. No other thread is included."""
    search_line = "external_search: on" if external_search else "external_search: off"
    current = [
        "CURRENT QUESTION:",
        question.strip(),
        search_line,
        FOLLOWUP_RULE,
    ]
    if not external_search:
        current.append(
            "The live search checkbox is off. Use the lesson panel only. "
            "Do not use an earlier paper summary."
        )
    blocks = [
        block
        for block in (packed_history.strip(), evidence_block.strip(), "\n".join(current))
        if block
    ]
    return "\n\n".join(blocks)


def turns_from_messages(messages: list[ChatMessage]) -> list[FollowupTurn]:
    turns: list[FollowupTurn] = []
    index = 0
    while index < len(messages):
        current = messages[index]
        if current.role != "user":
            index += 1
            continue
        nxt = messages[index + 1] if index + 1 < len(messages) else None
        assistant = nxt if nxt is not None and nxt.role == "assistant" else None
        turns.append(_turn_from_messages(current, assistant))
        index += 2 if assistant is not None else 1
    return turns


class SessionChatService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        text_model: TextModel | None = None,
        reranker: SessionReranker | None = None,
        reviewer: SessionReviewer | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._text_model = text_model
        self._reranker = reranker
        self._reviewer = reviewer
        self._threads = ChatThreadRepository(session)
        self._messages = ChatMessageRepository(session)

    async def get_thread(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> ChatThread | None:
        return await self._threads.get_in_workspace(thread_id=thread_id, workspace_id=workspace_id)

    async def thread_for_video(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> ChatThread | None:
        await self._require_video(workspace_id, video_id)
        return await self._threads.find_for_scope(
            workspace_id=workspace_id,
            scope_kind="video",
            scope_id=video_id,
        )

    async def list_messages(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[ChatMessage]:
        thread = await self.get_thread(thread_id=thread_id, workspace_id=workspace_id)
        if thread is None:
            raise SessionChatError(404, "NOT_FOUND", "Resource not found.")
        return await self._messages.list_for_thread(
            thread_id=thread.id,
            workspace_id=workspace_id,
            limit=200,
        )

    async def prepare(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        external_search: bool,
    ) -> tuple[ChatThread | None, str, list[uuid.UUID]]:
        """Pack prior turns for the new question. Does not create a thread or search."""
        await self._require_video(workspace_id, video_id)
        thread = await self._threads.find_for_scope(
            workspace_id=workspace_id,
            scope_kind="video",
            scope_id=video_id,
        )
        segment_ids = await self._segment_ids(workspace_id, video_id)
        if thread is None:
            return None, "", segment_ids
        messages = await self._messages.list_recent(
            thread_id=thread.id,
            workspace_id=workspace_id,
            limit=HISTORY_TURN_LIMIT * 4,
        )
        packed = pack_followup(turns_from_messages(messages), external_search=external_search)
        return thread, packed, segment_ids

    async def post_message(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        question: str,
        explanation_mode: str,
        external_search: bool,
        answer: dict[str, Any] | None,
    ) -> StoredTurn:
        cleaned = question.strip()
        if not cleaned:
            raise SessionChatError(422, "INVALID_QUESTION", "A question is required.")
        await self._require_video(workspace_id, video_id)
        thread = await self._ensure_thread(
            workspace_id=workspace_id,
            user_id=user_id,
            video_id=video_id,
        )
        await self._stamp_segments(
            workspace_id=workspace_id,
            video_id=video_id,
            thread_id=thread.id,
        )
        prior = await self._messages.list_recent(
            thread_id=thread.id,
            workspace_id=workspace_id,
            limit=HISTORY_TURN_LIMIT * 4,
        )
        packed = pack_followup(turns_from_messages(prior), external_search=external_search)
        packet = await self._packet(
            workspace_id=workspace_id,
            video_id=video_id,
            thread_id=thread.id,
            question=cleaned,
            external_search=external_search,
        )
        timings = await self._video_timings(packet.passages)
        try:
            if answer is None:
                draft = await self._draft_from_model(
                    packet,
                    packed_history=packed,
                    question=cleaned,
                    external_search=external_search,
                )
            else:
                draft = _structured_answer(answer, external_search=True)
            structured, review_status = await self._reviewed(
                packet,
                packed_history=packed,
                question=cleaned,
                external_search=external_search,
                draft=draft,
                timings=timings,
                fill_sources=answer is None,
            )
        except ReviewUnavailable:
            structured = withheld_answer()
            review_status = "withheld"
        structured["decision"] = packet.decision
        structured["kept"] = list(packet.kept)
        structured["review_status"] = review_status
        if not structured["lesson"]:
            raise SessionChatError(
                422,
                "LESSON_PANEL_REQUIRED",
                "The answer needs a lesson panel.",
            )
        user = await self._messages.create(
            thread_id=thread.id,
            workspace_id=workspace_id,
            role="user",
            content=cleaned,
            explanation_mode=explanation_mode,
            external_search_enabled=external_search,
        )
        assistant = await self._messages.create(
            thread_id=thread.id,
            workspace_id=workspace_id,
            role="assistant",
            content=_plain_text(structured),
            explanation_mode=explanation_mode,
            confidence_label="model",
            unsupported=False,
            content_json=structured,
        )
        if assistant.created_at <= user.created_at:
            assistant.created_at = user.created_at + timedelta(microseconds=1)
        await self._session.execute(
            update(ExternalEvidence)
            .where(
                ExternalEvidence.workspace_id == workspace_id,
                ExternalEvidence.thread_id == thread.id,
                ExternalEvidence.message_id.is_(None),
            )
            .values(message_id=user.id)
        )
        await self._session.flush()
        segment_ids = await self._segment_ids(workspace_id, video_id)
        logger.info(
            "lesson_chat_turn_stored",
            extra={
                "workspace_id": str(workspace_id),
                "video_id": str(video_id),
                "thread_id": str(thread.id),
                "external_search_enabled": external_search,
                "review_status": review_status,
                "prior_turns": min(len(turns_from_messages(prior)), HISTORY_TURN_LIMIT),
            },
        )
        return StoredTurn(
            thread=thread,
            user_message=user,
            assistant_message=assistant,
            segment_ids=segment_ids,
        )

    async def retrieve(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        question: str,
        external_search: bool,
        sources: list[SearchHitInput],
    ) -> tuple[ChatThread, EvidencePacket]:
        """Store this turn's search hits, index both origins, and decide the lanes."""
        cleaned = question.strip()
        if not cleaned:
            raise SessionChatError(422, "INVALID_QUESTION", "A question is required.")
        video = await self._require_video(workspace_id, video_id)
        thread = await self._ensure_thread(
            workspace_id=workspace_id,
            user_id=user_id,
            video_id=video_id,
        )
        await self._stamp_segments(
            workspace_id=workspace_id,
            video_id=video_id,
            thread_id=thread.id,
        )
        evidence = self._evidence_service()
        if external_search and sources:
            await evidence.store_hits(
                workspace_id=workspace_id,
                video_id=video_id,
                thread_id=thread.id,
                hits=sources,
            )
        packet = await evidence.build_packet(
            workspace_id=workspace_id,
            video_id=video_id,
            thread_id=thread.id,
            question=cleaned,
            external_search=external_search,
            watch_url=video.source_url or "",
        )
        return thread, packet

    async def _packet(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        thread_id: uuid.UUID,
        question: str,
        external_search: bool,
    ) -> EvidencePacket:
        video = await self._require_video(workspace_id, video_id)
        return await self._evidence_service().build_packet(
            workspace_id=workspace_id,
            video_id=video_id,
            thread_id=thread_id,
            question=question,
            external_search=external_search,
            watch_url=video.source_url or "",
        )

    def _evidence_service(self) -> SessionEvidenceService:
        return SessionEvidenceService(self._session, self._settings, reranker=self._reranker)

    async def _draft_from_model(
        self,
        packet: EvidencePacket,
        *,
        packed_history: str,
        question: str,
        external_search: bool,
    ) -> dict[str, Any]:
        if packet.decision == "abstain":
            return {
                "v": 1,
                "lesson": [{"heading": ABSTAIN_HEADING, "body": ABSTAIN_BODY}],
                "external": [],
                "sources": [],
            }
        prompt = model_user_input(
            packed_history=packed_history,
            question=question,
            external_search=external_search,
            evidence_block=packet.prompt_block,
        )
        payload = await self._complete(prompt)
        structured = _structured_answer(payload, external_search=True)
        if not packet.video_covered:
            structured["lesson"] = [{"heading": ABSTAIN_HEADING, "body": ABSTAIN_BODY}]
        return structured

    async def _reviewed(
        self,
        packet: EvidencePacket,
        *,
        packed_history: str,
        question: str,
        external_search: bool,
        draft: dict[str, Any],
        timings: dict[str, tuple[int | None, int | None]],
        fill_sources: bool,
    ) -> tuple[dict[str, Any], str]:
        request = build_review_request(
            question=question,
            decision=packet.decision,
            external_search=external_search,
            draft=draft,
            passages=list(packet.passages),
            timings=timings,
        )
        try:
            verdict = await self._judge(request)
        except ReviewUnavailable:
            return withheld_answer(), "withheld"
        if verdict.accept:
            return _normalize_draft(draft, packet, fill_sources=fill_sources), "accepted"
        try:
            rewritten = await self._regenerate(
                packet,
                packed_history=packed_history,
                question=question,
                external_search=external_search,
                reasons=verdict.reasons,
            )
            if packet.decision == "blend" and not rewritten.get("sources"):
                rewritten["sources"] = list(packet.sources)
            second_request = build_review_request(
                question=question,
                decision=packet.decision,
                external_search=external_search,
                draft=rewritten,
                passages=list(packet.passages),
                timings=timings,
            )
            second = await self._judge(second_request)
        except ReviewUnavailable:
            return withheld_answer(), "withheld"
        if second.accept:
            return _normalize_draft(rewritten, packet, fill_sources=True), "regenerated"
        return withheld_answer(), "withheld"

    async def _judge(self, request: ReviewRequest) -> ReviewVerdict:
        try:
            model_verdict = await self._active_reviewer().review(request)
        except ReviewUnavailable:
            raise
        except Exception as exc:
            if is_review_timeout(exc):
                raise ReviewUnavailable("Reviewer timed out.") from exc
            raise
        return merge_verdict(model_verdict, deterministic_reasons(request))

    def _active_reviewer(self) -> SessionReviewer:
        if self._reviewer is not None:
            return self._reviewer
        return ModelSessionReviewer(self._chat_model())

    def _chat_model(self) -> TextModel:
        model = self._text_model or build_text_model(self._settings)
        if is_retired_chat_model(str(getattr(model, "model", ""))):
            raise ReviewUnavailable("Retired chat model is skipped.")
        return model

    async def _regenerate(
        self,
        packet: EvidencePacket,
        *,
        packed_history: str,
        question: str,
        external_search: bool,
        reasons: tuple[str, ...],
    ) -> dict[str, Any]:
        prompt = model_user_input(
            packed_history=packed_history,
            question=question,
            external_search=external_search,
            evidence_block=packet.prompt_block,
        )
        prompt = f"{prompt}\n\n{rejection_note(reasons)}"
        payload = await self._complete(prompt)
        structured = _structured_answer(payload, external_search=True)
        if not packet.video_covered:
            structured["lesson"] = [{"heading": ABSTAIN_HEADING, "body": ABSTAIN_BODY}]
        return structured

    async def _video_timings(
        self,
        passages: tuple[Any, ...],
    ) -> dict[str, tuple[int | None, int | None]]:
        from app.retrieval.session_lanes import ORIGIN_VIDEO

        ids = [passage.id for passage in passages if passage.evidence_origin == ORIGIN_VIDEO]
        if not ids:
            return {}
        result = await self._session.execute(
            select(TranscriptSegment).where(TranscriptSegment.id.in_(ids))
        )
        return {str(row.id): (row.start_ms, row.end_ms) for row in result.scalars().all()}

    async def _complete(self, prompt: str) -> dict[str, Any]:
        model = self._chat_model()
        result = await model.generate_structured(
            ModelRequest(
                purpose="lesson_followup",
                instructions=(
                    "Return JSON with lesson and external arrays of heading and body. "
                    "Lesson text is the video. Outside text is not the video. " + FOLLOWUP_RULE
                ),
                user_input=prompt,
                evidence=[],
                response_schema=LESSON_FOLLOWUP_SCHEMA,
                max_output_tokens=1024,
                temperature=0.2,
                timeout_seconds=30,
                prompt_version="lesson-followup-v1",
            )
        )
        parsed = result.parsed if isinstance(result.parsed, dict) else {}
        return parsed

    async def _ensure_thread(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> ChatThread:
        existing = await self._threads.find_for_scope(
            workspace_id=workspace_id,
            scope_kind="video",
            scope_id=video_id,
        )
        if existing is not None:
            return existing
        return await self._threads.create(
            workspace_id=workspace_id,
            scope_kind="video",
            scope_id=video_id,
            created_by=user_id,
            title="Lesson chat",
        )

    async def _stamp_segments(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> None:
        """Set thread_id only. Segment ids, text, and timestamps stay as stored."""
        await self._session.execute(
            update(TranscriptSegment)
            .where(
                TranscriptSegment.workspace_id == workspace_id,
                TranscriptSegment.video_id == video_id,
            )
            .values(thread_id=thread_id)
        )
        await self._session.flush()

    async def _require_video(self, workspace_id: uuid.UUID, video_id: uuid.UUID) -> Video:
        result = await self._session.execute(
            select(Video).where(Video.id == video_id, Video.workspace_id == workspace_id)
        )
        video = result.scalar_one_or_none()
        if video is None:
            raise SessionChatError(404, "NOT_FOUND", "Resource not found.")
        return video

    async def _segment_ids(self, workspace_id: uuid.UUID, video_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(TranscriptSegment.id)
            .where(
                TranscriptSegment.workspace_id == workspace_id,
                TranscriptSegment.video_id == video_id,
            )
            .order_by(TranscriptSegment.ordinal.asc(), TranscriptSegment.id.asc())
        )
        return list(result.scalars().all())


def _turn_from_messages(user: ChatMessage, assistant: ChatMessage | None) -> FollowupTurn:
    raw = assistant.content_json if assistant is not None else None
    payload = raw if isinstance(raw, dict) else {}
    versioned = payload.get("v") == 1
    lesson = _sections(payload.get("lesson")) if versioned else ()
    if not lesson and assistant is not None and not versioned:
        text = (assistant.content or "").strip()
        if text:
            lesson = (FollowupSection(heading="Answer", body=text),)
    external = _sections(payload.get("external")) if versioned else ()
    sources = _sources(payload.get("sources")) if versioned else ()
    return FollowupTurn(
        question=user.content or "",
        lesson=lesson,
        external=external,
        sources=sources,
    )


def _sections(value: Any) -> tuple[FollowupSection, ...]:
    if not isinstance(value, list):
        return ()
    rows: list[FollowupSection] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading") or "").strip()
        body = str(item.get("body") or "").strip()
        if heading and body:
            rows.append(FollowupSection(heading=heading[:200], body=body[:8000]))
    return tuple(rows)


def _sources(value: Any) -> tuple[FollowupSource, ...]:
    if not isinstance(value, list):
        return ()
    rows: list[FollowupSource] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if provider not in SOURCE_PROVIDERS or not title or not url:
            continue
        rows.append(FollowupSource(provider=provider, title=title[:500], url=url[:2048]))
    return tuple(rows)


def _section_text(sections: tuple[FollowupSection, ...]) -> str:
    return "\n".join(f"{section.heading}: {section.body}" for section in sections)


def _source_text(sources: tuple[FollowupSource, ...]) -> str:
    return "\n".join(f"{source.provider} | {source.title} | {source.url}" for source in sources)


def _normalize_draft(
    draft: dict[str, Any],
    packet: EvidencePacket,
    *,
    fill_sources: bool,
) -> dict[str, Any]:
    blend = packet.decision == "blend"
    structured = _structured_answer(draft, external_search=blend)
    if fill_sources and blend and not structured["sources"]:
        structured["sources"] = list(packet.sources)
    if not blend:
        structured["external"] = []
        structured["sources"] = []
    return structured


def _structured_answer(payload: dict[str, Any], *, external_search: bool) -> dict[str, Any]:
    lesson = [
        {"heading": section.heading, "body": section.body}
        for section in _sections(payload.get("lesson"))
    ]
    if external_search:
        external = [
            {"heading": section.heading, "body": section.body}
            for section in _sections(payload.get("external"))
        ]
        sources = [
            {
                "provider": source.provider,
                "title": source.title,
                "url": source.url,
                "kind": _kind(item),
            }
            for item, source in _paired_sources(payload.get("sources"))
        ]
    else:
        external = []
        sources = []
    return {"v": 1, "lesson": lesson, "external": external, "sources": sources}


def _paired_sources(value: Any) -> list[tuple[dict[str, Any], FollowupSource]]:
    if not isinstance(value, list):
        return []
    pairs: list[tuple[dict[str, Any], FollowupSource]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        parsed = _sources([item])
        if parsed:
            pairs.append((item, parsed[0]))
    return pairs


def _kind(item: dict[str, Any]) -> str:
    kind = str(item.get("kind") or "other")
    if kind in {"paper", "official", "other"}:
        return kind
    return "other"


def _plain_text(structured: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("lesson", "external"):
        for section in _sections(structured.get(key)):
            chunks.append(f"{section.heading}\n{section.body}")
    return "\n\n".join(chunks) if chunks else "No lesson answer was produced."
