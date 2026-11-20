"""Evidence-grounded chat Q&A — retrieve, hydrate, validate, cite, persist."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import EmbeddingModel, ModelRequest, TextModel
from app.ai.factory import build_embedding_model, build_text_model
from app.core.observability.cost import estimate_provider_cost
from app.core.policies.ai_guardrails import AiGuardrailError, AiGuardrails
from app.core.policies.audit_policy import AuditRecord, get_audit_policy
from app.core.policies.output_policy import OutputPolicy
from app.core.policies.usage_policy import UsageQuotaExceeded, get_usage_policy
from app.core.settings import Settings
from app.db.models import SourceAsset, Video
from app.db.models.chat import ChatMessage, ChatThread, MessageCitation
from app.db.repositories import (
    ProviderRunRepository,
    SourceAssetRepository,
    TranscriptSegmentRepository,
    VideoRepository,
)
from app.db.repositories.chat import (
    ChatMessageRepository,
    ChatThreadRepository,
    MessageCitationRepository,
)
from app.domain.citation_urls import build_watch_url
from app.domain.evidence import (
    QaEvidenceItem,
    QaEvidencePacket,
    ValidatedQaAnswer,
    build_qa_packet,
    validate_qa_payload,
)
from app.domain.qa_prompts import (
    instructions_for,
    prompt_version,
    user_input_for,
    wrap_evidence_items,
)
from app.domain.qa_schemas import (
    GROUNDED_QA_JSON_SCHEMA,
    REFUSAL_MESSAGE,
    ExplanationMode,
)
from app.retrieval.contracts import SearchHit, SearchResult
from app.retrieval.factory import build_vector_store
from app.retrieval.filters import parse_uuid
from app.retrieval.profile import active_embedding_profile
from app.retrieval.query import HybridQueryService
from app.retrieval.scope import ScopeKind, resolve_authorized_video_ids
from app.services.usage import UsageService, WorkspaceQuotaExceeded

logger = logging.getLogger(__name__)

_SNIPPET_MAX = 280
_CONTEXT_TOKEN_BUDGET = 6_000
_CHARS_PER_TOKEN_EST = 4


class GroundedQaError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class CitationOut:
    citation_id: str
    video_id: uuid.UUID
    video_title: str
    segment_id: uuid.UUID
    snippet: str
    start_ms: int | None
    end_ms: int | None
    youtube_url: str | None
    timing_verified: bool


@dataclass(frozen=True, slots=True)
class GroundedAnswerResult:
    thread: ChatThread
    user_message: ChatMessage
    assistant_message: ChatMessage
    citations: list[CitationOut]
    answer: str
    claims: list[dict[str, Any]]
    analogies: list[dict[str, Any]]
    unsupported: bool
    confidence_label: str
    explanation_mode: ExplanationMode
    provider_run_id: uuid.UUID | None
    dropped_citation_ids: list[str]


class GroundedQaService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        text_model: TextModel | None = None,
        embedding_model: EmbeddingModel | None = None,
        query_service: HybridQueryService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._threads = ChatThreadRepository(session)
        self._messages = ChatMessageRepository(session)
        self._citations = MessageCitationRepository(session)
        self._videos = VideoRepository(session)
        self._assets = SourceAssetRepository(session)
        self._segments = TranscriptSegmentRepository(session)
        self._runs = ProviderRunRepository(session)
        self._text = text_model
        self._embed = embedding_model
        self._query = query_service

    def _text_model(self) -> TextModel:
        if self._text is None:
            self._text = build_text_model(self._settings)
        return self._text

    def _query_service(self) -> HybridQueryService:
        if self._query is not None:
            return self._query
        store = build_vector_store(self._settings)
        profile = active_embedding_profile(self._settings)
        embedder = self._embed or build_embedding_model(self._settings)
        self._embed = embedder
        self._query = HybridQueryService(
            store=store,
            embedder=embedder,
            profile=profile,
            settings=self._settings,
        )
        return self._query

    async def create_thread(
        self,
        *,
        workspace_id: uuid.UUID,
        created_by: uuid.UUID,
        scope_kind: ScopeKind,
        scope_id: uuid.UUID | None,
        title: str | None = None,
    ) -> ChatThread:
        # Authorize scope up-front so threads never bind unauthorized resources.
        try:
            await resolve_authorized_video_ids(
                self._session,
                workspace_id=workspace_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
            )
        except Exception as exc:  # mapped below
            from app.retrieval.errors import UnauthorizedScopeError

            if isinstance(exc, UnauthorizedScopeError):
                raise GroundedQaError(404, "NOT_FOUND", "Resource not found.") from exc
            raise
        return await self._threads.create(
            workspace_id=workspace_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            created_by=created_by,
            title=title,
        )

    async def get_thread(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> ChatThread | None:
        return await self._threads.get_in_workspace(
            thread_id=thread_id,
            workspace_id=workspace_id,
        )

    async def list_messages(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
        limit: int = 50,
        after_id: uuid.UUID | None = None,
    ) -> tuple[list[ChatMessage], dict[uuid.UUID, list[MessageCitation]]]:
        thread = await self.get_thread(thread_id=thread_id, workspace_id=workspace_id)
        if thread is None:
            raise GroundedQaError(404, "NOT_FOUND", "Resource not found.")
        messages = await self._messages.list_for_thread(
            thread_id=thread_id,
            workspace_id=workspace_id,
            limit=limit,
            after_id=after_id,
        )
        cites = await self._citations.list_for_messages(
            message_ids=[m.id for m in messages],
            workspace_id=workspace_id,
        )
        by_msg: dict[uuid.UUID, list[MessageCitation]] = {}
        for c in cites:
            by_msg.setdefault(c.message_id, []).append(c)
        return messages, by_msg

    async def ask(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
        question: str,
        explanation_mode: ExplanationMode = ExplanationMode.STANDARD,
        actor_user_id: uuid.UUID | None = None,
    ) -> GroundedAnswerResult:
        try:
            question_clean = AiGuardrails.enforce_user_text(
                question,
                max_characters=self._settings.ai_max_input_characters,
                code="QUESTION_TOO_LONG",
            )
        except AiGuardrailError as exc:
            oversized = {"QUESTION_TOO_LONG", "PAYLOAD_TOO_LARGE", "INPUT_TOO_LARGE"}
            status = 413 if exc.code in oversized else 422
            code = "INVALID_QUESTION" if exc.code == "EMPTY_INPUT" else exc.code
            raise GroundedQaError(status, code, exc.message) from exc

        usage = get_usage_policy()
        if actor_user_id is not None:
            try:
                usage.check_chat_allowed(str(actor_user_id))
            except UsageQuotaExceeded as exc:
                raise GroundedQaError(429, exc.code, exc.message) from exc

        workspace_usage = UsageService(self._session, self._settings)
        try:
            await workspace_usage.check_request_allowed(workspace_id)
        except WorkspaceQuotaExceeded as exc:
            raise GroundedQaError(429, exc.code, exc.message) from exc

        thread = await self.get_thread(thread_id=thread_id, workspace_id=workspace_id)
        if thread is None:
            get_audit_policy().record(
                AuditRecord(
                    action="authorization_denied",
                    workspace_id=workspace_id,
                    actor_user_id=actor_user_id,
                    resource_type="chat_thread",
                    resource_id=str(thread_id),
                    metadata={"reason": "cross_tenant_or_missing"},
                )
            )
            raise GroundedQaError(404, "NOT_FOUND", "Resource not found.")

        scope_kind = thread.scope_kind  # type: ignore[assignment]
        if scope_kind not in {"video", "playlist", "library"}:
            raise GroundedQaError(422, "INVALID_SCOPE", "Thread scope is invalid.")

        user_msg = await self._messages.create(
            thread_id=thread.id,
            workspace_id=workspace_id,
            role="user",
            content=question_clean,
            explanation_mode=explanation_mode.value,
        )

        try:
            authorized = await resolve_authorized_video_ids(
                self._session,
                workspace_id=workspace_id,
                scope_kind=scope_kind,  # type: ignore[arg-type]
                scope_id=thread.scope_id,
            )
        except Exception as exc:
            from app.retrieval.errors import UnauthorizedScopeError

            if isinstance(exc, UnauthorizedScopeError):
                raise GroundedQaError(404, "NOT_FOUND", "Resource not found.") from exc
            raise

        search = await self._query_service().search_authorized(
            authorized=authorized,
            query_text=question_clean,
        )
        packet = await self._hydrate_evidence(
            workspace_id=workspace_id,
            scope_kind=authorized.scope_kind,
            scope_id=authorized.scope_id,
            authorized_video_ids=authorized.video_ids,
            search=search,
        )

        if not packet.allowed_segment_ids:
            validated = ValidatedQaAnswer(
                answer=REFUSAL_MESSAGE,
                claims=[],
                analogies=[],
                unsupported=True,
                confidence_label="abstain",
                cited_segment_ids=[],
                dropped_citation_ids=[],
                refused=True,
            )
            return await self._persist_answer(
                thread=thread,
                user_message=user_msg,
                workspace_id=workspace_id,
                explanation_mode=explanation_mode,
                validated=validated,
                packet=packet,
                provider_run_id=None,
                request_hash=_request_hash(question_clean, explanation_mode.value, []),
            )

        evidence_items = [
            {
                "id": item.segment_id,
                "segment_id": item.segment_id,
                "text": item.text,
            }
            for item in packet.items_by_id.values()
        ]
        evidence_blob = wrap_evidence_items(evidence_items)
        model = self._text_model()
        started = time.perf_counter()
        try:
            result = await model.generate_structured(
                ModelRequest(
                    purpose="grounded_qa",
                    instructions=instructions_for(
                        explanation_mode,
                        scope=f"{authorized.scope_kind}",
                    ),
                    user_input=(
                        f"{user_input_for(question=question_clean, mode=explanation_mode)}"
                        f"\n\n{evidence_blob}"
                    ),
                    evidence=evidence_items,
                    response_schema=GROUNDED_QA_JSON_SCHEMA,
                    max_output_tokens=min(self._settings.ai_max_output_tokens, 1800),
                    temperature=0.0,
                    timeout_seconds=self._settings.ai_request_timeout_seconds,
                    prompt_version=prompt_version(),
                )
            )
        except AiGuardrailError as exc:
            status = 413 if "TOO_LARGE" in exc.code else 422
            raise GroundedQaError(status, exc.code, exc.message) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        # OutputPolicy: strip unsafe URLs / minimize PII before citation membership checks.
        sanitized_payload = OutputPolicy.sanitize_payload_strings(
            result.parsed if isinstance(result.parsed, dict) else {}
        )
        validated = validate_qa_payload(
            sanitized_payload,
            packet,
            refusal_message=REFUSAL_MESSAGE,
        )
        # Deterministic post-validation: never present fabricated citations as grounded.
        if validated.dropped_citation_ids and not validated.refused:
            get_audit_policy().record(
                AuditRecord(
                    action="citation_dropped",
                    workspace_id=workspace_id,
                    actor_user_id=actor_user_id,
                    resource_type="chat_thread",
                    resource_id=str(thread_id),
                    metadata={"dropped_count": len(validated.dropped_citation_ids)},
                )
            )
        req_hash = _request_hash(
            question_clean,
            explanation_mode.value,
            sorted(packet.allowed_segment_ids),
        )
        # Exactly-once spend effect via request_hash: cache hits skip ledger increment.
        existing_run = await self._runs.find_by_request_hash(
            workspace_id=workspace_id,
            request_hash=req_hash,
        )
        if existing_run is not None:
            run = existing_run
        else:
            run = await self._runs.create(
                workspace_id=workspace_id,
                provider=result.usage.provider,
                model=result.usage.model,
                operation="grounded_qa",
                request_hash=req_hash,
                prompt_version=prompt_version(),
                token_in=result.usage.input_tokens,
                token_out=result.usage.output_tokens,
                latency_ms=latency_ms,
                status="succeeded",
                metadata_json={
                    "scope_kind": authorized.scope_kind,
                    "hit_count": len(search.hits),
                    "evidence_count": len(packet.allowed_segment_ids),
                    "dropped_citation_ids": validated.dropped_citation_ids[:20],
                    "refused": validated.refused,
                    # Candidate IDs/scores only — no raw transcript in routine telemetry.
                    "retrieval": self._query_service().result_telemetry(search),
                },
            )
            estimate = estimate_provider_cost(
                provider=result.usage.provider,
                model=result.usage.model,
                token_in=result.usage.input_tokens,
                token_out=result.usage.output_tokens,
            )
            await workspace_usage.record_provider_usage(
                workspace_id,
                token_in=result.usage.input_tokens,
                token_out=result.usage.output_tokens,
                estimate_usd=estimate.estimate_usd,
                effect_key=req_hash,
            )
        return await self._persist_answer(
            thread=thread,
            user_message=user_msg,
            workspace_id=workspace_id,
            explanation_mode=explanation_mode,
            validated=validated,
            packet=packet,
            provider_run_id=run.id,
            request_hash=req_hash,
        )

    async def _hydrate_evidence(
        self,
        *,
        workspace_id: uuid.UUID,
        scope_kind: str,
        scope_id: uuid.UUID | None,
        authorized_video_ids: tuple[uuid.UUID, ...],
        search: SearchResult,
    ) -> QaEvidencePacket:
        """Hydrate Qdrant hits from Postgres; drop stale / unauthorized / over-budget."""
        candidate_ids = _collect_segment_ids(search.hits)
        if not candidate_ids:
            return build_qa_packet(
                workspace_id=workspace_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                items=[],
            )

        # Current revision per video from latest source asset.
        revision_by_video: dict[uuid.UUID, int] = {}
        asset_by_video: dict[uuid.UUID, SourceAsset] = {}
        for vid in authorized_video_ids:
            asset = await self._assets.latest_for_video(
                video_id=vid,
                workspace_id=workspace_id,
            )
            if asset is not None:
                revision_by_video[vid] = asset.source_revision
                asset_by_video[vid] = asset

        # Payload revision must match current asset revision when present.
        allowed_from_hits: set[uuid.UUID] = set()
        for hit in search.hits:
            payload = hit.payload or {}
            try:
                video_id = parse_uuid(payload.get("video_id"), field_name="video_id")
            except Exception:
                continue
            if video_id not in revision_by_video:
                continue
            try:
                payload_ws = parse_uuid(payload.get("workspace_id"), field_name="workspace_id")
            except Exception:
                continue
            if payload_ws != workspace_id:
                continue
            payload_rev = payload.get("source_revision")
            if payload_rev is not None and int(payload_rev) != revision_by_video[video_id]:
                continue
            for raw_sid in payload.get("segment_ids") or []:
                try:
                    sid = parse_uuid(raw_sid, field_name="segment_id")
                except Exception:
                    continue
                if sid in candidate_ids:
                    allowed_from_hits.add(sid)

        segments = await self._segments.get_by_ids_in_workspace(
            segment_ids=allowed_from_hits,
            workspace_id=workspace_id,
            video_ids=authorized_video_ids,
        )
        # Bound context: keep ordinal order, stop near token budget.
        budget_chars = _CONTEXT_TOKEN_BUDGET * _CHARS_PER_TOKEN_EST
        used = 0
        items: list[QaEvidenceItem] = []
        video_cache: dict[uuid.UUID, Video] = {}
        for seg in segments:
            if used >= budget_chars:
                break
            video = video_cache.get(seg.video_id)
            if video is None:
                loaded = await self._videos.get_in_workspace(
                    video_id=seg.video_id,
                    workspace_id=workspace_id,
                )
                if loaded is None:
                    continue
                video_cache[seg.video_id] = loaded
                video = loaded
            asset = asset_by_video.get(seg.video_id)
            if asset is None:
                continue
            # Segment must belong to current asset revision.
            if seg.asset_id != asset.id:
                continue
            text = (seg.text or "").strip()
            if not text:
                continue
            items.append(
                QaEvidenceItem(
                    segment_id=str(seg.id),
                    video_id=seg.video_id,
                    text=text,
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    source_revision=asset.source_revision,
                    youtube_video_id=video.youtube_video_id,
                    video_title=video.title,
                    timecode_quality=asset.timecode_quality,
                )
            )
            used += len(text)

        return build_qa_packet(
            workspace_id=workspace_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            items=items,
        )

    async def _persist_answer(
        self,
        *,
        thread: ChatThread,
        user_message: ChatMessage,
        workspace_id: uuid.UUID,
        explanation_mode: ExplanationMode,
        validated: ValidatedQaAnswer,
        packet: QaEvidencePacket,
        provider_run_id: uuid.UUID | None,
        request_hash: str,
    ) -> GroundedAnswerResult:
        citation_rows: list[dict[str, Any]] = []
        citation_outs: list[CitationOut] = []
        for idx, sid in enumerate(validated.cited_segment_ids, start=1):
            item = packet.items_by_id.get(sid)
            if item is None:
                continue
            link = build_watch_url(
                youtube_video_id=item.youtube_video_id,
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                timecode_quality=item.timecode_quality,
            )
            key = f"c_{idx:02d}"
            snippet = item.text[:_SNIPPET_MAX]
            citation_rows.append(
                {
                    "segment_id": uuid.UUID(sid),
                    "video_id": item.video_id,
                    "citation_key": key,
                    "snippet": snippet,
                    "start_ms": link.start_ms,
                    "end_ms": link.end_ms,
                    "timing_verified": link.timing_verified,
                    "youtube_url": link.youtube_url,
                }
            )
            citation_outs.append(
                CitationOut(
                    citation_id=key,
                    video_id=item.video_id,
                    video_title=item.video_title,
                    segment_id=uuid.UUID(sid),
                    snippet=snippet,
                    start_ms=link.start_ms,
                    end_ms=link.end_ms,
                    youtube_url=link.youtube_url,
                    timing_verified=link.timing_verified,
                )
            )

        content_json = {
            "claims": validated.claims,
            "analogies": validated.analogies,
            "unsupported": validated.unsupported,
            "confidence_label": validated.confidence_label,
            "dropped_citation_ids": validated.dropped_citation_ids[:20],
            "request_hash": request_hash,
            "prompt_version": prompt_version(),
            "origin": (
                "fixture_data"
                if (self._text is not None and self._text.provider == "fake")
                or self._settings.ai_chat_provider.strip().lower() == "fake"
                else "model"
            ),
        }
        safe_answer = OutputPolicy.sanitize_assistant_text(validated.answer)
        assistant = await self._messages.create(
            thread_id=thread.id,
            workspace_id=workspace_id,
            role="assistant",
            content=safe_answer,
            explanation_mode=explanation_mode.value,
            provider_run_id=provider_run_id,
            confidence_label=validated.confidence_label,
            unsupported=validated.unsupported,
            content_json=content_json,
        )
        if citation_rows:
            await self._citations.create_many(
                message_id=assistant.id,
                workspace_id=workspace_id,
                citations=citation_rows,
            )

        logger.info(
            "grounded_qa completed",
            extra={
                "workspace_id": str(workspace_id),
                "thread_id": str(thread.id),
                "unsupported": validated.unsupported,
                "citation_count": len(citation_outs),
                "dropped_count": len(validated.dropped_citation_ids),
            },
        )
        return GroundedAnswerResult(
            thread=thread,
            user_message=user_message,
            assistant_message=assistant,
            citations=citation_outs,
            answer=safe_answer,
            claims=validated.claims,
            analogies=validated.analogies,
            unsupported=validated.unsupported,
            confidence_label=validated.confidence_label,
            explanation_mode=explanation_mode,
            provider_run_id=provider_run_id,
            dropped_citation_ids=validated.dropped_citation_ids,
        )


def _collect_segment_ids(hits: list[SearchHit]) -> set[uuid.UUID]:
    out: set[uuid.UUID] = set()
    for hit in hits:
        for raw in (hit.payload or {}).get("segment_ids") or []:
            try:
                out.add(parse_uuid(raw, field_name="segment_id"))
            except Exception:
                continue
    return out


def _request_hash(question: str, mode: str, evidence_ids: list[str]) -> str:
    raw = "|".join([question, mode, ",".join(evidence_ids), prompt_version()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
