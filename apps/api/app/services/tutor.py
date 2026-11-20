"""Source-grounded tutor/quiz generation, attempts, spaced review, concept graph."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ModelRequest, TextModel
from app.ai.factory import build_text_model
from app.core.policies.audit_policy import AuditRecord, get_audit_policy
from app.core.settings import Settings
from app.db.base import utcnow
from app.db.models.tutor import (
    Concept,
    ConceptEdge,
    LearnerProgress,
    QuizAttempt,
    ReviewSchedule,
    StudyDeck,
    StudyItem,
)
from app.db.repositories import (
    SourceAssetRepository,
    TranscriptSegmentRepository,
    VideoRepository,
)
from app.db.repositories.summaries import ProviderRunRepository
from app.db.repositories.tutor import (
    ConceptEdgeRepository,
    ConceptRepository,
    LearnerProgressRepository,
    QuizAttemptRepository,
    ReviewScheduleRepository,
    StudyDeckRepository,
    StudyItemRepository,
    TutorPreferenceRepository,
)
from app.domain.citation_urls import build_watch_url, timing_is_verified
from app.domain.spaced_review import ReviewGrade, advance_schedule, initial_schedule
from app.domain.tutor_prompts import (
    instructions_for,
    prompt_version,
    user_input_for,
    wrap_evidence_items,
)
from app.domain.tutor_schemas import (
    EFFICACY_DISCLAIMER,
    TUTOR_DECK_JSON_SCHEMA,
    PresentationLanguage,
)
from app.domain.tutor_validate import TutorValidationError, validate_tutor_payload

logger = logging.getLogger(__name__)

_SNIPPET_MAX = 280
_MAX_EVIDENCE_SEGMENTS = 40


class TutorError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class EvidenceCite:
    segment_id: uuid.UUID
    snippet: str
    start_ms: int | None
    end_ms: int | None
    youtube_url: str | None
    timing_verified: bool


@dataclass(frozen=True, slots=True)
class DeckBundle:
    deck: StudyDeck
    items: list[StudyItem]
    concepts: list[Concept]
    edges: list[ConceptEdge]
    evidence: dict[str, EvidenceCite]
    disclaimer: str


class TutorService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        text_model: TextModel | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._text = text_model or build_text_model(settings)
        self._videos = VideoRepository(session)
        self._assets = SourceAssetRepository(session)
        self._segments = TranscriptSegmentRepository(session)
        self._decks = StudyDeckRepository(session)
        self._items = StudyItemRepository(session)
        self._attempts = QuizAttemptRepository(session)
        self._reviews = ReviewScheduleRepository(session)
        self._progress = LearnerProgressRepository(session)
        self._prefs = TutorPreferenceRepository(session)
        self._concepts = ConceptRepository(session)
        self._edges = ConceptEdgeRepository(session)
        self._runs = ProviderRunRepository(session)

    async def generate_deck(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        presentation_language: str | None = None,
    ) -> DeckBundle:
        video = await self._videos.get_in_workspace(
            video_id=video_id, workspace_id=workspace_id
        )
        if video is None:
            get_audit_policy().record(
                AuditRecord(
                    action="authorization_denied",
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    resource_type="video",
                    resource_id=str(video_id),
                    metadata={"reason": "cross_tenant_or_missing", "action": "tutor_generate"},
                )
            )
            raise TutorError(404, "NOT_FOUND", "Resource not found.")

        asset = await self._assets.latest_for_video(
            video_id=video_id, workspace_id=workspace_id
        )
        if asset is None:
            raise TutorError(
                409,
                "SOURCE_TRANSCRIPT_REQUIRED",
                "Upload a permitted transcript before generating practice content.",
            )

        rows = await self._segments.list_for_asset(
            asset_id=asset.id, workspace_id=workspace_id
        )
        if not rows:
            raise TutorError(
                409,
                "SOURCE_TRANSCRIPT_REQUIRED",
                "No transcript segments available for practice generation.",
            )

        lang = await self._resolve_language(
            workspace_id=workspace_id,
            user_id=user_id,
            override=presentation_language,
        )

        capped = rows[:_MAX_EVIDENCE_SEGMENTS]
        evidence_items = wrap_evidence_items(
            [
                {
                    "id": str(r.id),
                    "text": r.text,
                    "ordinal": r.ordinal,
                    "start_ms": r.start_ms,
                    "end_ms": r.end_ms,
                }
                for r in capped
            ]
        )
        allowed = frozenset(str(r.id) for r in capped)

        request = ModelRequest(
            purpose="tutor_quiz",
            prompt_version=prompt_version(),
            instructions=instructions_for(presentation_language=lang),
            user_input=user_input_for(
                video_title=video.title or "Untitled video",
                presentation_language=lang.value,
            ),
            evidence=evidence_items,
            response_schema=TUTOR_DECK_JSON_SCHEMA,
            max_output_tokens=min(self._settings.ai_max_output_tokens, 1800),
            temperature=0.0,
            timeout_seconds=self._settings.ai_request_timeout_seconds,
        )
        result = await self._text.generate_structured(request)
        payload = result.parsed if isinstance(result.parsed, dict) else {}

        try:
            validated = validate_tutor_payload(payload, allowed_segment_ids=allowed)
        except TutorValidationError as exc:
            raise TutorError(422, exc.code, exc.message) from exc

        if validated.blocked_unsupported or not validated.items:
            raise TutorError(
                422,
                "TUTOR_UNSUPPORTED_EVIDENCE",
                "Generated practice content cited no verified transcript evidence.",
            )

        run = await self._runs.create(
            workspace_id=workspace_id,
            provider=getattr(self._text, "provider", "fake"),
            model=getattr(self._text, "model", "unknown"),
            operation="tutor_quiz",
            request_hash=str(uuid.uuid5(uuid.NAMESPACE_URL, f"tutor:{video_id}:{user_id}")),
            prompt_version=prompt_version(),
            token_in=int(getattr(result.usage, "input_tokens", 0) or 0),
            token_out=int(getattr(result.usage, "output_tokens", 0) or 0),
            latency_ms=0,
            status="succeeded",
        )

        deck = await self._decks.create(
            workspace_id=workspace_id,
            user_id=user_id,
            video_id=video_id,
            title=validated.title,
            presentation_language=lang.value,
            source_revision=asset.source_revision,
            origin=validated.origin,
            provider_run_id=run.id if run else None,
        )

        concept_map: dict[str, Concept] = {}
        for concept in validated.concepts:
            row = await self._concepts.upsert(
                workspace_id=workspace_id,
                video_id=video_id,
                canonical_name=concept["name"],
                description=concept["description"],
                evidence_segment_ids=concept["evidence_segment_ids"],
                created_by=user_id,
            )
            concept_map[concept["name"].lower()] = row

        for concept in validated.concepts:
            dst = concept_map.get(concept["name"].lower())
            if dst is None:
                continue
            for prereq_name in concept.get("prerequisites") or []:
                src = concept_map.get(str(prereq_name).lower())
                if src is None or src.id == dst.id:
                    continue
                evidence_span = None
                eids = concept.get("evidence_segment_ids") or []
                if eids:
                    try:
                        evidence_span = uuid.UUID(str(eids[0]))
                    except ValueError:
                        evidence_span = None
                await self._edges.upsert_prerequisite(
                    workspace_id=workspace_id,
                    src_concept_id=src.id,
                    dst_concept_id=dst.id,
                    evidence_span_id=evidence_span,
                )

        items: list[StudyItem] = []
        now = utcnow()
        for ordinal, raw in enumerate(validated.items):
            concept_id = None
            cname = raw.get("concept_name")
            if cname:
                mapped = concept_map.get(str(cname).lower())
                if mapped is not None:
                    concept_id = mapped.id
            item = await self._items.create(
                deck_id=deck.id,
                workspace_id=workspace_id,
                user_id=user_id,
                item_kind=str(raw["item_kind"]),
                ordinal=ordinal,
                prompt=str(raw["prompt"]),
                answer=str(raw["answer"]),
                explanation=str(raw.get("explanation") or ""),
                explanation_origin=str(raw.get("explanation_origin") or "source_supported"),
                choices_json=list(raw.get("choices") or []) or None,
                correct_choice_index=raw.get("correct_choice_index"),
                evidence_segment_ids=list(raw["evidence_segment_ids"]),
                presentation_json=raw.get("presentation") or None,
                concept_id=concept_id,
            )
            items.append(item)
            init = initial_schedule(now=now)
            await self._reviews.upsert(
                workspace_id=workspace_id,
                user_id=user_id,
                item_id=item.id,
                due_at=init.due_at,
                interval_days=init.interval_days,
                ease_factor=init.ease_factor,
                repetitions=init.repetitions,
                last_result=None,
                last_reviewed_at=None,
            )

        await self._progress.get_or_create(
            workspace_id=workspace_id,
            user_id=user_id,
            video_id=video_id,
            deck_id=deck.id,
        )

        get_audit_policy().record(
            AuditRecord(
                action="tutor_deck_generated",
                workspace_id=workspace_id,
                actor_user_id=user_id,
                resource_type="study_deck",
                resource_id=str(deck.id),
                metadata={
                    "video_id": str(video_id),
                    "item_count": len(items),
                    "dropped_citations": len(validated.dropped_citation_ids),
                },
            )
        )

        return await self._bundle_deck(deck, items=items)

    async def list_decks(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID | None = None,
    ) -> list[StudyDeck]:
        return await self._decks.list_for_user(
            workspace_id=workspace_id, user_id=user_id, video_id=video_id
        )

    async def get_deck(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        deck_id: uuid.UUID,
    ) -> DeckBundle:
        deck = await self._decks.get_for_user(
            deck_id=deck_id, workspace_id=workspace_id, user_id=user_id
        )
        if deck is None:
            raise TutorError(404, "NOT_FOUND", "Resource not found.")
        items = await self._items.list_for_deck(
            deck_id=deck.id, workspace_id=workspace_id, user_id=user_id
        )
        return await self._bundle_deck(deck, items=items)

    async def delete_deck(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        deck_id: uuid.UUID,
    ) -> None:
        ok = await self._decks.delete_for_user(
            deck_id=deck_id, workspace_id=workspace_id, user_id=user_id
        )
        if not ok:
            raise TutorError(404, "NOT_FOUND", "Resource not found.")
        get_audit_policy().record(
            AuditRecord(
                action="tutor_deck_deleted",
                workspace_id=workspace_id,
                actor_user_id=user_id,
                resource_type="study_deck",
                resource_id=str(deck_id),
                metadata={},
            )
        )

    async def submit_attempt(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        deck_id: uuid.UUID,
        item_id: uuid.UUID,
        selected_choice_index: int | None = None,
        response_text: str | None = None,
    ) -> tuple[QuizAttempt, StudyItem, list[EvidenceCite]]:
        deck = await self._decks.get_for_user(
            deck_id=deck_id, workspace_id=workspace_id, user_id=user_id
        )
        if deck is None:
            raise TutorError(404, "NOT_FOUND", "Resource not found.")
        item = await self._items.get_for_user(
            item_id=item_id, workspace_id=workspace_id, user_id=user_id
        )
        if item is None or item.deck_id != deck.id:
            raise TutorError(404, "NOT_FOUND", "Resource not found.")

        eids = [str(x) for x in (item.evidence_segment_ids or [])]
        cites = await self._hydrate_evidence(
            workspace_id=workspace_id,
            video_id=deck.video_id,
            segment_ids=eids,
            timecode_quality=None,
        )
        evidence_resolved = bool(cites) and len(cites) == len(eids)

        is_correct = False
        if item.item_kind == "quiz":
            if selected_choice_index is None:
                raise TutorError(
                    422,
                    "QUIZ_CHOICE_REQUIRED",
                    "selected_choice_index is required for quiz items.",
                )
            is_correct = selected_choice_index == item.correct_choice_index
        else:
            # Flashcard self-grade: non-empty response counts as seen; correctness optional.
            is_correct = bool((response_text or "").strip()) or selected_choice_index == 0

        attempt = await self._attempts.create(
            workspace_id=workspace_id,
            user_id=user_id,
            deck_id=deck.id,
            item_id=item.id,
            selected_choice_index=selected_choice_index,
            response_text=response_text,
            is_correct=is_correct,
            evidence_resolved=evidence_resolved,
            evidence_segment_ids=eids,
        )
        await self._progress.record_attempt(
            workspace_id=workspace_id,
            user_id=user_id,
            video_id=deck.video_id,
            deck_id=deck.id,
            is_correct=is_correct,
        )
        return attempt, item, cites

    async def list_due_reviews(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[tuple[ReviewSchedule, StudyItem]]:
        due = await self._reviews.list_due(
            workspace_id=workspace_id,
            user_id=user_id,
            as_of=datetime.now(UTC),
            limit=limit,
        )
        out: list[tuple[ReviewSchedule, StudyItem]] = []
        for sched in due:
            item = await self._items.get_for_user(
                item_id=sched.item_id, workspace_id=workspace_id, user_id=user_id
            )
            if item is not None:
                out.append((sched, item))
        return out

    async def submit_review(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
        grade: ReviewGrade,
    ) -> tuple[ReviewSchedule, StudyItem]:
        item = await self._items.get_for_user(
            item_id=item_id, workspace_id=workspace_id, user_id=user_id
        )
        if item is None:
            raise TutorError(404, "NOT_FOUND", "Resource not found.")
        existing = await self._reviews.get_for_item(
            workspace_id=workspace_id, user_id=user_id, item_id=item_id
        )
        if existing is None:
            base = initial_schedule()
            interval, ease, reps = base.interval_days, base.ease_factor, base.repetitions
        else:
            interval, ease, reps = (
                existing.interval_days,
                existing.ease_factor,
                existing.repetitions,
            )
        nxt = advance_schedule(
            interval_days=interval,
            ease_factor=ease,
            repetitions=reps,
            grade=grade,
        )
        now = utcnow()
        sched = await self._reviews.upsert(
            workspace_id=workspace_id,
            user_id=user_id,
            item_id=item_id,
            due_at=nxt.due_at,
            interval_days=nxt.interval_days,
            ease_factor=nxt.ease_factor,
            repetitions=nxt.repetitions,
            last_result=nxt.last_result,
            last_reviewed_at=now,
        )
        deck = await self._decks.get_for_user(
            deck_id=item.deck_id, workspace_id=workspace_id, user_id=user_id
        )
        if deck is not None:
            await self._progress.record_review(
                workspace_id=workspace_id,
                user_id=user_id,
                video_id=deck.video_id,
                deck_id=deck.id,
            )
        return sched, item

    async def list_progress(
        self, *, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[LearnerProgress]:
        return await self._progress.list_for_user(
            workspace_id=workspace_id, user_id=user_id
        )

    async def list_concepts(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID | None = None,
    ) -> tuple[list[Concept], list[ConceptEdge]]:
        concepts = await self._concepts.list_for_workspace(
            workspace_id=workspace_id, video_id=video_id
        )
        edges = await self._edges.list_for_workspace(workspace_id=workspace_id)
        concept_ids = {c.id for c in concepts}
        filtered = [
            e
            for e in edges
            if e.src_concept_id in concept_ids and e.dst_concept_id in concept_ids
        ]
        return concepts, filtered

    async def get_preferences(
        self, *, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> PresentationLanguage:
        pref = await self._prefs.get(workspace_id=workspace_id, user_id=user_id)
        if pref is None:
            return PresentationLanguage.EN
        try:
            return PresentationLanguage(pref.presentation_language)
        except ValueError:
            return PresentationLanguage.EN

    async def set_preferences(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        presentation_language: str,
    ) -> PresentationLanguage:
        try:
            lang = PresentationLanguage(presentation_language)
        except ValueError as exc:
            raise TutorError(
                422,
                "INVALID_PRESENTATION_LANGUAGE",
                "presentation_language must be 'en' or 'ta'.",
            ) from exc
        await self._prefs.upsert(
            workspace_id=workspace_id,
            user_id=user_id,
            presentation_language=lang.value,
        )
        return lang

    async def _resolve_language(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        override: str | None,
    ) -> PresentationLanguage:
        if override:
            try:
                return PresentationLanguage(override)
            except ValueError as exc:
                raise TutorError(
                    422,
                    "INVALID_PRESENTATION_LANGUAGE",
                    "presentation_language must be 'en' or 'ta'.",
                ) from exc
        return await self.get_preferences(workspace_id=workspace_id, user_id=user_id)

    async def _bundle_deck(
        self, deck: StudyDeck, *, items: list[StudyItem] | None = None
    ) -> DeckBundle:
        item_rows = items or await self._items.list_for_deck(
            deck_id=deck.id,
            workspace_id=deck.workspace_id,
            user_id=deck.user_id,
        )
        all_ids: list[str] = []
        for it in item_rows:
            for sid in it.evidence_segment_ids or []:
                s = str(sid)
                if s not in all_ids:
                    all_ids.append(s)
        asset = await self._assets.latest_for_video(
            video_id=deck.video_id, workspace_id=deck.workspace_id
        )
        tcq = asset.timecode_quality if asset else None
        evidence = {
            str(c.segment_id): c
            for c in await self._hydrate_evidence(
                workspace_id=deck.workspace_id,
                video_id=deck.video_id,
                segment_ids=all_ids,
                timecode_quality=tcq,
            )
        }
        concepts, edges = await self.list_concepts(
            workspace_id=deck.workspace_id, video_id=deck.video_id
        )
        return DeckBundle(
            deck=deck,
            items=item_rows,
            concepts=concepts,
            edges=edges,
            evidence=evidence,
            disclaimer=EFFICACY_DISCLAIMER,
        )

    async def _hydrate_evidence(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        segment_ids: list[str],
        timecode_quality: str | None,
    ) -> list[EvidenceCite]:
        if not segment_ids:
            return []
        uuids: list[uuid.UUID] = []
        for sid in segment_ids:
            try:
                uuids.append(uuid.UUID(str(sid)))
            except ValueError:
                continue
        if not uuids:
            return []
        video = await self._videos.get_in_workspace(
            video_id=video_id, workspace_id=workspace_id
        )
        youtube_id = video.youtube_video_id if video else None
        tcq = timecode_quality
        if tcq is None:
            asset = await self._assets.latest_for_video(
                video_id=video_id, workspace_id=workspace_id
            )
            tcq = asset.timecode_quality if asset else None
        rows = await self._segments.get_by_ids_in_workspace(
            segment_ids=uuids,
            workspace_id=workspace_id,
            video_ids=[video_id],
        )
        by_id = {r.id: r for r in rows}
        out: list[EvidenceCite] = []
        for seg_uuid in uuids:
            seg = by_id.get(seg_uuid)
            if seg is None:
                continue
            link = build_watch_url(
                youtube_video_id=youtube_id,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                timecode_quality=tcq,
            )
            verified = timing_is_verified(
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                timecode_quality=tcq,
            )
            snippet = (seg.text or "")[:_SNIPPET_MAX]
            out.append(
                EvidenceCite(
                    segment_id=seg.id,
                    snippet=snippet,
                    start_ms=link.start_ms if verified else None,
                    end_ms=link.end_ms if verified else None,
                    youtube_url=link.youtube_url,
                    timing_verified=verified,
                )
            )
        return out
