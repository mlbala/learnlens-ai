"""Chapter, summary, and provider_run repositories (workspace-scoped)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability.cost import estimate_provider_cost
from app.db.models import Chapter, ProviderRun, Summary


class ChapterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_video(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
        source_revision: int,
        chapters: list[dict[str, Any]],
    ) -> list[Chapter]:
        await self._session.execute(
            delete(Chapter).where(
                Chapter.video_id == video_id,
                Chapter.workspace_id == workspace_id,
            )
        )
        rows: list[Chapter] = []
        for item in chapters:
            start_id = item.get("start_segment_id")
            end_id = item.get("end_segment_id")
            # Deterministic IDs so chapter-scope summary cache keys stay stable
            # across identical re-runs of unchanged source content.
            chapter_id = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"chapter:{video_id}:{source_revision}:{start_id}:{end_id}",
            )
            row = Chapter(
                id=chapter_id,
                video_id=video_id,
                workspace_id=workspace_id,
                source_revision=source_revision,
                title=str(item["title"])[:300],
                start_segment_id=start_id,
                end_segment_id=end_id,
                topic_json=item.get("topic_json"),
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return rows

    async def list_for_video(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[Chapter]:
        result = await self._session.execute(
            select(Chapter)
            .where(
                Chapter.video_id == video_id,
                Chapter.workspace_id == workspace_id,
            )
            .order_by(Chapter.created_at.asc())
        )
        return list(result.scalars().all())


class ProviderRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        provider: str,
        model: str,
        operation: str,
        request_hash: str,
        prompt_version: str,
        token_in: int | None,
        token_out: int | None,
        latency_ms: int | None,
        status: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> ProviderRun:
        estimate = estimate_provider_cost(
            provider=provider,
            model=model,
            token_in=token_in,
            token_out=token_out,
        )
        meta = dict(metadata_json or {})
        meta.setdefault("cost_estimate_version", estimate.estimate_version)
        meta.setdefault("cost_is_estimate", True)
        meta.setdefault("cost_disclaimer", estimate.disclaimer)
        row = ProviderRun(
            workspace_id=workspace_id,
            provider=provider,
            model=model,
            operation=operation,
            request_hash=request_hash,
            prompt_version=prompt_version,
            token_in=token_in,
            token_out=token_out,
            cost_estimate_usd=estimate.estimate_usd,
            latency_ms=latency_ms,
            status=status,
            metadata_json=meta,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def find_by_request_hash(
        self,
        *,
        workspace_id: uuid.UUID,
        request_hash: str,
    ) -> ProviderRun | None:
        result = await self._session.execute(
            select(ProviderRun)
            .where(
                ProviderRun.workspace_id == workspace_id,
                ProviderRun.request_hash == request_hash,
                ProviderRun.status == "succeeded",
            )
            .order_by(ProviderRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class SummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_cache_key(
        self,
        *,
        workspace_id: uuid.UUID,
        cache_key: str,
    ) -> Summary | None:
        result = await self._session.execute(
            select(Summary)
            .where(
                Summary.workspace_id == workspace_id,
                Summary.cache_key == cache_key,
                Summary.status.in_(["ready", "blocked"]),
            )
            .order_by(Summary.revision.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        workspace_id: uuid.UUID,
        scope_kind: str,
        scope_id: uuid.UUID,
        summary_kind: str,
        revision: int,
        content_json: dict[str, Any],
        coverage_json: dict[str, Any] | None,
        provider_run_id: uuid.UUID | None,
        cache_key: str,
        status: str,
    ) -> Summary:
        existing = await self._session.execute(
            select(Summary).where(
                Summary.workspace_id == workspace_id,
                Summary.scope_kind == scope_kind,
                Summary.scope_id == scope_id,
                Summary.summary_kind == summary_kind,
                Summary.revision == revision,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = Summary(
                workspace_id=workspace_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                summary_kind=summary_kind,
                revision=revision,
                content_json=content_json,
                coverage_json=coverage_json,
                provider_run_id=provider_run_id,
                cache_key=cache_key,
                status=status,
            )
            self._session.add(row)
        else:
            row.content_json = content_json
            row.coverage_json = coverage_json
            row.provider_run_id = provider_run_id
            row.cache_key = cache_key
            row.status = status
        await self._session.flush()
        return row

    async def list_for_scope(
        self,
        *,
        workspace_id: uuid.UUID,
        scope_kind: str,
        scope_id: uuid.UUID,
        summary_kind: str | None = None,
    ) -> list[Summary]:
        stmt = select(Summary).where(
            Summary.workspace_id == workspace_id,
            Summary.scope_kind == scope_kind,
            Summary.scope_id == scope_id,
        )
        if summary_kind:
            stmt = stmt.where(Summary.summary_kind == summary_kind)
        stmt = stmt.order_by(Summary.summary_kind.asc(), Summary.revision.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
