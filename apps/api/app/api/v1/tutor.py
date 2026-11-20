"""Tutor / quiz / spaced-review / concept-graph APIs (phase 18)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from app.api.deps import CsrfAuth, CurrentAuth, DbSession, SettingsDep
from app.api.v1.schemas import (
    ConceptEdgeOut,
    ConceptGraphResponse,
    ConceptOut,
    GenerateTutorDeckRequest,
    LearnerProgressListResponse,
    LearnerProgressOut,
    QuizAttemptOut,
    QuizAttemptRequest,
    ReviewItemOut,
    ReviewListResponse,
    ReviewSubmitRequest,
    StudyDeckListResponse,
    StudyDeckOut,
    StudyItemOut,
    TutorEvidenceOut,
    TutorPreferencesOut,
    TutorPreferencesUpdate,
)
from app.core.errors import raise_api_error
from app.domain.spaced_review import ReviewGrade
from app.domain.tutor_schemas import EFFICACY_DISCLAIMER
from app.services.tutor import DeckBundle, EvidenceCite, TutorError, TutorService

router = APIRouter(prefix="/api/v1/tutor", tags=["tutor"])


def _map_error(exc: TutorError, request_id: str | None) -> None:
    raise_api_error(
        exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=request_id,
    )


def _evidence_out(c: EvidenceCite) -> TutorEvidenceOut:
    return TutorEvidenceOut(
        segment_id=c.segment_id,
        snippet=c.snippet,
        start_ms=c.start_ms,
        end_ms=c.end_ms,
        youtube_url=c.youtube_url,
        timing_verified=c.timing_verified,
    )


def _item_out(item: Any, evidence_map: dict[str, EvidenceCite]) -> StudyItemOut:
    eids = [str(x) for x in (item.evidence_segment_ids or [])]
    cites = [_evidence_out(evidence_map[eid]) for eid in eids if eid in evidence_map]
    return StudyItemOut(
        id=item.id,
        deck_id=item.deck_id,
        item_kind=item.item_kind,
        ordinal=item.ordinal,
        prompt=item.prompt,
        answer=item.answer,
        explanation=item.explanation,
        explanation_origin=item.explanation_origin,
        choices=list(item.choices_json or []),
        correct_choice_index=item.correct_choice_index,
        evidence_segment_ids=eids,
        evidence=cites,
        presentation=dict(item.presentation_json or {}),
        concept_id=item.concept_id,
    )


def _deck_out(bundle: DeckBundle, *, include_items: bool = True) -> StudyDeckOut:
    deck = bundle.deck
    items = (
        [_item_out(it, bundle.evidence) for it in bundle.items] if include_items else []
    )
    return StudyDeckOut(
        id=deck.id,
        workspace_id=deck.workspace_id,
        user_id=deck.user_id,
        video_id=deck.video_id,
        title=deck.title,
        presentation_language=deck.presentation_language,
        source_revision=deck.source_revision,
        status=deck.status,
        origin=deck.origin,
        items=items,
        concepts=[
            ConceptOut(
                id=c.id,
                workspace_id=c.workspace_id,
                video_id=c.video_id,
                canonical_name=c.canonical_name,
                description=c.description,
                evidence_segment_ids=[str(x) for x in (c.evidence_segment_ids or [])],
            )
            for c in bundle.concepts
        ],
        concept_edges=[
            ConceptEdgeOut(
                id=e.id,
                src_concept_id=e.src_concept_id,
                dst_concept_id=e.dst_concept_id,
                relation=e.relation,
                evidence_span_id=e.evidence_span_id,
            )
            for e in bundle.edges
        ],
        disclaimer=bundle.disclaimer,
        created_at=deck.created_at,
    )


@router.post("/decks", response_model=StudyDeckOut)
async def generate_deck(
    body: GenerateTutorDeckRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> StudyDeckOut:
    service = TutorService(db, settings)
    try:
        bundle = await service.generate_deck(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            video_id=body.video_id,
            presentation_language=body.presentation_language,
        )
    except TutorError as exc:
        _map_error(exc, getattr(request.state, "request_id", None))
        raise
    return _deck_out(bundle)


@router.get("/decks", response_model=StudyDeckListResponse)
async def list_decks(
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    video_id: Annotated[uuid.UUID | None, Query()] = None,
) -> StudyDeckListResponse:
    service = TutorService(db, settings)
    decks = await service.list_decks(
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        video_id=video_id,
    )
    items: list[StudyDeckOut] = []
    for deck in decks:
        bundle = await service.get_deck(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            deck_id=deck.id,
        )
        items.append(_deck_out(bundle, include_items=False))
    return StudyDeckListResponse(items=items, disclaimer=EFFICACY_DISCLAIMER)


@router.get("/decks/{deck_id}", response_model=StudyDeckOut)
async def get_deck(
    deck_id: uuid.UUID,
    request: Request,
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
) -> StudyDeckOut:
    service = TutorService(db, settings)
    try:
        bundle = await service.get_deck(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            deck_id=deck_id,
        )
    except TutorError as exc:
        _map_error(exc, getattr(request.state, "request_id", None))
        raise
    return _deck_out(bundle)


@router.delete("/decks/{deck_id}", status_code=204)
async def delete_deck(
    deck_id: uuid.UUID,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> None:
    service = TutorService(db, settings)
    try:
        await service.delete_deck(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            deck_id=deck_id,
        )
    except TutorError as exc:
        _map_error(exc, getattr(request.state, "request_id", None))
        raise


@router.post("/decks/{deck_id}/attempts", response_model=QuizAttemptOut)
async def submit_attempt(
    deck_id: uuid.UUID,
    body: QuizAttemptRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> QuizAttemptOut:
    service = TutorService(db, settings)
    try:
        attempt, item, cites = await service.submit_attempt(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            deck_id=deck_id,
            item_id=body.item_id,
            selected_choice_index=body.selected_choice_index,
            response_text=body.response_text,
        )
    except TutorError as exc:
        _map_error(exc, getattr(request.state, "request_id", None))
        raise
    return QuizAttemptOut(
        id=attempt.id,
        deck_id=attempt.deck_id,
        item_id=attempt.item_id,
        is_correct=attempt.is_correct,
        evidence_resolved=attempt.evidence_resolved,
        evidence=[_evidence_out(c) for c in cites],
        explanation=item.explanation,
        explanation_origin=item.explanation_origin,
        correct_choice_index=item.correct_choice_index,
        created_at=attempt.created_at,
    )


@router.get("/review", response_model=ReviewListResponse)
async def list_review(
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReviewListResponse:
    service = TutorService(db, settings)
    due = await service.list_due_reviews(
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        limit=limit,
    )
    items: list[ReviewItemOut] = []
    for sched, item in due:
        empty_map: dict[str, EvidenceCite] = {}
        items.append(
            ReviewItemOut(
                schedule_id=sched.id,
                item=_item_out(item, empty_map),
                due_at=sched.due_at,
                interval_days=sched.interval_days,
                ease_factor=sched.ease_factor,
                repetitions=sched.repetitions,
                last_result=sched.last_result,
            )
        )
    return ReviewListResponse(items=items, disclaimer=EFFICACY_DISCLAIMER)


@router.post("/review/{item_id}", response_model=ReviewItemOut)
async def submit_review(
    item_id: uuid.UUID,
    body: ReviewSubmitRequest,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> ReviewItemOut:
    service = TutorService(db, settings)
    grade: ReviewGrade = body.grade  # type: ignore[assignment]
    try:
        sched, item = await service.submit_review(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            item_id=item_id,
            grade=grade,
        )
    except TutorError as exc:
        _map_error(exc, getattr(request.state, "request_id", None))
        raise
    return ReviewItemOut(
        schedule_id=sched.id,
        item=_item_out(item, {}),
        due_at=sched.due_at,
        interval_days=sched.interval_days,
        ease_factor=sched.ease_factor,
        repetitions=sched.repetitions,
        last_result=sched.last_result,
    )


@router.get("/progress", response_model=LearnerProgressListResponse)
async def list_progress(
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
) -> LearnerProgressListResponse:
    service = TutorService(db, settings)
    rows = await service.list_progress(
        workspace_id=ctx.workspace.id, user_id=ctx.user.id
    )
    return LearnerProgressListResponse(
        items=[
            LearnerProgressOut(
                id=r.id,
                workspace_id=r.workspace_id,
                user_id=r.user_id,
                video_id=r.video_id,
                deck_id=r.deck_id,
                items_seen=r.items_seen,
                items_correct=r.items_correct,
                reviews_completed=r.reviews_completed,
                last_activity_at=r.last_activity_at,
                disclaimer=r.disclaimer,
            )
            for r in rows
        ],
        disclaimer=EFFICACY_DISCLAIMER,
    )


@router.get("/concepts", response_model=ConceptGraphResponse)
async def list_concepts(
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    video_id: Annotated[uuid.UUID | None, Query()] = None,
) -> ConceptGraphResponse:
    service = TutorService(db, settings)
    concepts, edges = await service.list_concepts(
        workspace_id=ctx.workspace.id, video_id=video_id
    )
    return ConceptGraphResponse(
        concepts=[
            ConceptOut(
                id=c.id,
                workspace_id=c.workspace_id,
                video_id=c.video_id,
                canonical_name=c.canonical_name,
                description=c.description,
                evidence_segment_ids=[str(x) for x in (c.evidence_segment_ids or [])],
            )
            for c in concepts
        ],
        edges=[
            ConceptEdgeOut(
                id=e.id,
                src_concept_id=e.src_concept_id,
                dst_concept_id=e.dst_concept_id,
                relation=e.relation,
                evidence_span_id=e.evidence_span_id,
            )
            for e in edges
        ],
    )


@router.get("/preferences", response_model=TutorPreferencesOut)
async def get_preferences(
    ctx: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
) -> TutorPreferencesOut:
    service = TutorService(db, settings)
    lang = await service.get_preferences(
        workspace_id=ctx.workspace.id, user_id=ctx.user.id
    )
    return TutorPreferencesOut(presentation_language=lang.value)


@router.put("/preferences", response_model=TutorPreferencesOut)
async def update_preferences(
    body: TutorPreferencesUpdate,
    request: Request,
    ctx: CsrfAuth,
    db: DbSession,
    settings: SettingsDep,
) -> TutorPreferencesOut:
    service = TutorService(db, settings)
    try:
        lang = await service.set_preferences(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            presentation_language=body.presentation_language,
        )
    except TutorError as exc:
        _map_error(exc, getattr(request.state, "request_id", None))
        raise
    return TutorPreferencesOut(presentation_language=lang.value)
