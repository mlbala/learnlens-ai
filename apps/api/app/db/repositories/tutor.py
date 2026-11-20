"""Tutor/quiz/concept repositories — always scoped by workspace (+ user where owned)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.models.tutor import (
    Concept,
    ConceptEdge,
    LearnerProgress,
    QuizAttempt,
    ReviewSchedule,
    StudyDeck,
    StudyItem,
    TutorPreference,
)
from app.domain.tutor_schemas import EFFICACY_DISCLAIMER


class ConceptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID | None,
        canonical_name: str,
        description: str,
        evidence_segment_ids: list[str],
        created_by: uuid.UUID | None,
    ) -> Concept:
        result = await self._session.execute(
            select(Concept).where(
                Concept.workspace_id == workspace_id,
                Concept.canonical_name == canonical_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = Concept(
                workspace_id=workspace_id,
                video_id=video_id,
                canonical_name=canonical_name,
                description=description,
                evidence_segment_ids=evidence_segment_ids,
                created_by=created_by,
            )
            self._session.add(row)
        else:
            row.description = description
            row.evidence_segment_ids = evidence_segment_ids
            if video_id is not None:
                row.video_id = video_id
        await self._session.flush()
        return row

    async def list_for_workspace(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID | None = None,
    ) -> list[Concept]:
        stmt = select(Concept).where(Concept.workspace_id == workspace_id)
        if video_id is not None:
            stmt = stmt.where(Concept.video_id == video_id)
        stmt = stmt.order_by(Concept.canonical_name.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(
        self, *, workspace_id: uuid.UUID, canonical_name: str
    ) -> Concept | None:
        result = await self._session.execute(
            select(Concept).where(
                Concept.workspace_id == workspace_id,
                Concept.canonical_name == canonical_name,
            )
        )
        return result.scalar_one_or_none()


class ConceptEdgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_prerequisite(
        self,
        *,
        workspace_id: uuid.UUID,
        src_concept_id: uuid.UUID,
        dst_concept_id: uuid.UUID,
        evidence_span_id: uuid.UUID | None = None,
    ) -> ConceptEdge:
        result = await self._session.execute(
            select(ConceptEdge).where(
                ConceptEdge.workspace_id == workspace_id,
                ConceptEdge.src_concept_id == src_concept_id,
                ConceptEdge.dst_concept_id == dst_concept_id,
                ConceptEdge.relation == "prerequisite",
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ConceptEdge(
                workspace_id=workspace_id,
                src_concept_id=src_concept_id,
                dst_concept_id=dst_concept_id,
                relation="prerequisite",
                evidence_span_id=evidence_span_id,
            )
            self._session.add(row)
            await self._session.flush()
        return row

    async def list_for_workspace(
        self, *, workspace_id: uuid.UUID
    ) -> list[ConceptEdge]:
        result = await self._session.execute(
            select(ConceptEdge)
            .where(ConceptEdge.workspace_id == workspace_id)
            .order_by(ConceptEdge.created_at.asc())
        )
        return list(result.scalars().all())


class StudyDeckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        title: str,
        presentation_language: str,
        source_revision: int,
        origin: str = "fixture_data",
        provider_run_id: uuid.UUID | None = None,
        status: str = "ready",
    ) -> StudyDeck:
        row = StudyDeck(
            workspace_id=workspace_id,
            user_id=user_id,
            video_id=video_id,
            title=title,
            presentation_language=presentation_language,
            source_revision=source_revision,
            origin=origin,
            provider_run_id=provider_run_id,
            status=status,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_for_user(
        self,
        *,
        deck_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> StudyDeck | None:
        result = await self._session.execute(
            select(StudyDeck).where(
                StudyDeck.id == deck_id,
                StudyDeck.workspace_id == workspace_id,
                StudyDeck.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[StudyDeck]:
        stmt = (
            select(StudyDeck)
            .where(
                StudyDeck.workspace_id == workspace_id,
                StudyDeck.user_id == user_id,
            )
            .order_by(StudyDeck.created_at.desc())
            .limit(limit)
        )
        if video_id is not None:
            stmt = stmt.where(StudyDeck.video_id == video_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_user(
        self,
        *,
        deck_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        row = await self.get_for_user(
            deck_id=deck_id, workspace_id=workspace_id, user_id=user_id
        )
        if row is None:
            return False
        await self._session.execute(
            delete(StudyDeck).where(
                StudyDeck.id == deck_id,
                StudyDeck.workspace_id == workspace_id,
                StudyDeck.user_id == user_id,
            )
        )
        await self._session.flush()
        return True


class StudyItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        deck_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        item_kind: str,
        ordinal: int,
        prompt: str,
        answer: str,
        explanation: str,
        explanation_origin: str,
        choices_json: list[Any] | None,
        correct_choice_index: int | None,
        evidence_segment_ids: list[str],
        presentation_json: dict[str, Any] | None,
        concept_id: uuid.UUID | None,
    ) -> StudyItem:
        row = StudyItem(
            deck_id=deck_id,
            workspace_id=workspace_id,
            user_id=user_id,
            item_kind=item_kind,
            ordinal=ordinal,
            prompt=prompt,
            answer=answer,
            explanation=explanation,
            explanation_origin=explanation_origin,
            choices_json=choices_json,
            correct_choice_index=correct_choice_index,
            evidence_segment_ids=evidence_segment_ids,
            presentation_json=presentation_json,
            concept_id=concept_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_deck(
        self,
        *,
        deck_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[StudyItem]:
        result = await self._session.execute(
            select(StudyItem)
            .where(
                StudyItem.deck_id == deck_id,
                StudyItem.workspace_id == workspace_id,
                StudyItem.user_id == user_id,
            )
            .order_by(StudyItem.ordinal.asc())
        )
        return list(result.scalars().all())

    async def get_for_user(
        self,
        *,
        item_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> StudyItem | None:
        result = await self._session.execute(
            select(StudyItem).where(
                StudyItem.id == item_id,
                StudyItem.workspace_id == workspace_id,
                StudyItem.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


class QuizAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        deck_id: uuid.UUID,
        item_id: uuid.UUID,
        selected_choice_index: int | None,
        response_text: str | None,
        is_correct: bool,
        evidence_resolved: bool,
        evidence_segment_ids: list[str],
    ) -> QuizAttempt:
        row = QuizAttempt(
            workspace_id=workspace_id,
            user_id=user_id,
            deck_id=deck_id,
            item_id=item_id,
            selected_choice_index=selected_choice_index,
            response_text=response_text,
            is_correct=is_correct,
            evidence_resolved=evidence_resolved,
            evidence_segment_ids=evidence_segment_ids,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_user(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        deck_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[QuizAttempt]:
        stmt = (
            select(QuizAttempt)
            .where(
                QuizAttempt.workspace_id == workspace_id,
                QuizAttempt.user_id == user_id,
            )
            .order_by(QuizAttempt.created_at.desc())
            .limit(limit)
        )
        if deck_id is not None:
            stmt = stmt.where(QuizAttempt.deck_id == deck_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ReviewScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
        due_at: datetime,
        interval_days: float,
        ease_factor: float,
        repetitions: int,
        last_result: str | None,
        last_reviewed_at: datetime | None,
    ) -> ReviewSchedule:
        result = await self._session.execute(
            select(ReviewSchedule).where(
                ReviewSchedule.workspace_id == workspace_id,
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.item_id == item_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ReviewSchedule(
                workspace_id=workspace_id,
                user_id=user_id,
                item_id=item_id,
                due_at=due_at,
                interval_days=interval_days,
                ease_factor=ease_factor,
                repetitions=repetitions,
                last_result=last_result,
                last_reviewed_at=last_reviewed_at,
            )
            self._session.add(row)
        else:
            row.due_at = due_at
            row.interval_days = interval_days
            row.ease_factor = ease_factor
            row.repetitions = repetitions
            row.last_result = last_result
            row.last_reviewed_at = last_reviewed_at
        await self._session.flush()
        return row

    async def get_for_item(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> ReviewSchedule | None:
        result = await self._session.execute(
            select(ReviewSchedule).where(
                ReviewSchedule.workspace_id == workspace_id,
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.item_id == item_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_due(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        as_of: datetime,
        limit: int = 50,
    ) -> list[ReviewSchedule]:
        result = await self._session.execute(
            select(ReviewSchedule)
            .where(
                ReviewSchedule.workspace_id == workspace_id,
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.due_at <= as_of,
            )
            .order_by(ReviewSchedule.due_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


class LearnerProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        deck_id: uuid.UUID | None = None,
    ) -> LearnerProgress:
        result = await self._session.execute(
            select(LearnerProgress).where(
                LearnerProgress.workspace_id == workspace_id,
                LearnerProgress.user_id == user_id,
                LearnerProgress.video_id == video_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = LearnerProgress(
                workspace_id=workspace_id,
                user_id=user_id,
                video_id=video_id,
                deck_id=deck_id,
                disclaimer=EFFICACY_DISCLAIMER,
            )
            self._session.add(row)
            await self._session.flush()
        elif deck_id is not None:
            row.deck_id = deck_id
        return row

    async def record_attempt(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        deck_id: uuid.UUID,
        is_correct: bool,
    ) -> LearnerProgress:
        row = await self.get_or_create(
            workspace_id=workspace_id,
            user_id=user_id,
            video_id=video_id,
            deck_id=deck_id,
        )
        row.items_seen += 1
        if is_correct:
            row.items_correct += 1
        row.last_activity_at = utcnow()
        await self._session.flush()
        return row

    async def record_review(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        deck_id: uuid.UUID | None,
    ) -> LearnerProgress:
        row = await self.get_or_create(
            workspace_id=workspace_id,
            user_id=user_id,
            video_id=video_id,
            deck_id=deck_id,
        )
        row.reviews_completed += 1
        row.last_activity_at = utcnow()
        await self._session.flush()
        return row

    async def list_for_user(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[LearnerProgress]:
        result = await self._session.execute(
            select(LearnerProgress)
            .where(
                LearnerProgress.workspace_id == workspace_id,
                LearnerProgress.user_id == user_id,
            )
            .order_by(LearnerProgress.updated_at.desc())
        )
        return list(result.scalars().all())


class TutorPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, *, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> TutorPreference | None:
        result = await self._session.execute(
            select(TutorPreference).where(
                TutorPreference.workspace_id == workspace_id,
                TutorPreference.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        presentation_language: str,
    ) -> TutorPreference:
        row = await self.get(workspace_id=workspace_id, user_id=user_id)
        if row is None:
            row = TutorPreference(
                workspace_id=workspace_id,
                user_id=user_id,
                presentation_language=presentation_language,
            )
            self._session.add(row)
        else:
            row.presentation_language = presentation_language
        await self._session.flush()
        return row
