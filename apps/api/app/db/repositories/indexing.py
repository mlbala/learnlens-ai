"""Index manifest repository — workspace-scoped derived index tracking."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.models.indexing import IndexManifest


class IndexManifestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_ready(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        embedding_profile: str,
        source_revision: int,
        qdrant_collection: str,
        chunk_count: int,
        processing_version: str,
        previous_collection: str | None = None,
    ) -> IndexManifest:
        existing = await self.get(
            workspace_id=workspace_id,
            video_id=video_id,
            embedding_profile=embedding_profile,
            source_revision=source_revision,
        )
        if existing is None:
            row = IndexManifest(
                workspace_id=workspace_id,
                video_id=video_id,
                embedding_profile=embedding_profile,
                source_revision=source_revision,
                qdrant_collection=qdrant_collection,
                chunk_count=chunk_count,
                status="ready",
                processing_version=processing_version,
                activated_at=utcnow(),
                previous_collection=previous_collection,
            )
            self._session.add(row)
            await self._session.flush()
            return row

        existing.qdrant_collection = qdrant_collection
        existing.chunk_count = chunk_count
        existing.status = "ready"
        existing.processing_version = processing_version
        existing.activated_at = utcnow()
        if previous_collection is not None:
            existing.previous_collection = previous_collection
        await self._session.flush()
        return existing

    async def get(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        embedding_profile: str,
        source_revision: int,
    ) -> IndexManifest | None:
        result = await self._session.execute(
            select(IndexManifest).where(
                IndexManifest.workspace_id == workspace_id,
                IndexManifest.video_id == video_id,
                IndexManifest.embedding_profile == embedding_profile,
                IndexManifest.source_revision == source_revision,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_video(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> list[IndexManifest]:
        result = await self._session.execute(
            select(IndexManifest)
            .where(
                IndexManifest.workspace_id == workspace_id,
                IndexManifest.video_id == video_id,
            )
            .order_by(IndexManifest.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_superseded(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        embedding_profile: str,
    ) -> int:
        """Mark older ready manifests for a profile as superseded (safe reindex)."""
        rows = await self.list_for_video(workspace_id=workspace_id, video_id=video_id)
        updated = 0
        for row in rows:
            if row.embedding_profile == embedding_profile and row.status == "ready":
                row.status = "superseded"
                updated += 1
        if updated:
            await self._session.flush()
        return updated
