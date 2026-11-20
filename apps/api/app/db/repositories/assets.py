"""Source asset and transcript segment repositories (workspace-scoped)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SourceAsset, TranscriptSegment
from app.domain.transcript_parse import ParsedCue


class SourceAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
        source_kind: str,
        storage_key: str,
        content_hash: str,
        rights_attested_at: datetime,
        uploaded_by: uuid.UUID,
        timecode_quality: str,
        source_revision: int,
    ) -> SourceAsset:
        asset = SourceAsset(
            video_id=video_id,
            workspace_id=workspace_id,
            source_kind=source_kind,
            storage_key=storage_key,
            content_hash=content_hash,
            rights_attested_at=rights_attested_at,
            uploaded_by=uploaded_by,
            timecode_quality=timecode_quality,
            source_revision=source_revision,
        )
        self._session.add(asset)
        await self._session.flush()
        return asset

    async def get_in_workspace(
        self,
        *,
        asset_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> SourceAsset | None:
        result = await self._session.execute(
            select(SourceAsset).where(
                SourceAsset.id == asset_id,
                SourceAsset.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def next_revision(self, *, video_id: uuid.UUID, workspace_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(SourceAsset.source_revision), 0)).where(
                SourceAsset.video_id == video_id,
                SourceAsset.workspace_id == workspace_id,
            )
        )
        current = int(result.scalar_one())
        return current + 1

    async def find_by_hash(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
        content_hash: str,
    ) -> SourceAsset | None:
        result = await self._session.execute(
            select(SourceAsset)
            .where(
                SourceAsset.video_id == video_id,
                SourceAsset.workspace_id == workspace_id,
                SourceAsset.content_hash == content_hash,
            )
            .order_by(SourceAsset.source_revision.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def latest_for_video(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> SourceAsset | None:
        result = await self._session.execute(
            select(SourceAsset)
            .where(
                SourceAsset.video_id == video_id,
                SourceAsset.workspace_id == workspace_id,
            )
            .order_by(SourceAsset.source_revision.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class TranscriptSegmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_asset(
        self,
        *,
        asset_id: uuid.UUID,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
        cues: list[ParsedCue] | tuple[ParsedCue, ...],
    ) -> list[TranscriptSegment]:
        await self._session.execute(
            delete(TranscriptSegment).where(TranscriptSegment.asset_id == asset_id)
        )
        rows: list[TranscriptSegment] = []
        for cue in cues:
            digest = hashlib.sha256(
                f"{cue.ordinal}|{cue.start_ms}|{cue.end_ms}|{cue.text}".encode()
            ).hexdigest()
            row = TranscriptSegment(
                asset_id=asset_id,
                video_id=video_id,
                workspace_id=workspace_id,
                ordinal=cue.ordinal,
                text=cue.text,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                speaker=None,
                content_hash=digest,
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return rows

    async def list_for_asset(
        self,
        *,
        asset_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[TranscriptSegment]:
        result = await self._session.execute(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.asset_id == asset_id,
                TranscriptSegment.workspace_id == workspace_id,
            )
            .order_by(TranscriptSegment.ordinal.asc())
        )
        return list(result.scalars().all())
