"""Media asset and frame repositories (workspace-scoped)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MediaAsset, MediaFrame


class MediaAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        media_kind: str,
        storage_key: str,
        content_hash: str,
        content_type: str,
        size_bytes: int,
        filename: str,
        rights_attested_at: datetime,
        provider_transfer_consented_at: datetime,
        uploaded_by: uuid.UUID,
        antivirus_status: str,
        status: str = "queued",
    ) -> MediaAsset:
        row = MediaAsset(
            workspace_id=workspace_id,
            video_id=video_id,
            media_kind=media_kind,
            storage_key=storage_key,
            content_hash=content_hash,
            content_type=content_type,
            size_bytes=size_bytes,
            filename=filename,
            rights_attested_at=rights_attested_at,
            provider_transfer_consented_at=provider_transfer_consented_at,
            uploaded_by=uploaded_by,
            antivirus_status=antivirus_status,
            status=status,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_in_workspace(
        self,
        *,
        media_asset_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> MediaAsset | None:
        result = await self._session.execute(
            select(MediaAsset).where(
                MediaAsset.id == media_asset_id,
                MediaAsset.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_video(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[MediaAsset]:
        result = await self._session.execute(
            select(MediaAsset).where(
                MediaAsset.video_id == video_id,
                MediaAsset.workspace_id == workspace_id,
            )
        )
        return list(result.scalars().all())

    async def update_result(
        self,
        asset: MediaAsset,
        *,
        status: str,
        source_asset_id: uuid.UUID | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> MediaAsset:
        asset.status = status
        if source_asset_id is not None:
            asset.source_asset_id = source_asset_id
        if result_json is not None:
            asset.result_json = result_json
        await self._session.flush()
        return asset

    async def delete_for_video(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[MediaAsset]:
        rows = await self.list_for_video(video_id=video_id, workspace_id=workspace_id)
        await self._session.execute(
            delete(MediaAsset).where(
                MediaAsset.video_id == video_id,
                MediaAsset.workspace_id == workspace_id,
            )
        )
        await self._session.flush()
        return rows


class MediaFrameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_asset(
        self,
        *,
        media_asset_id: uuid.UUID,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
        frames: list[dict[str, Any]],
    ) -> list[MediaFrame]:
        await self._session.execute(
            delete(MediaFrame).where(MediaFrame.media_asset_id == media_asset_id)
        )
        rows: list[MediaFrame] = []
        for item in frames:
            row = MediaFrame(
                media_asset_id=media_asset_id,
                workspace_id=workspace_id,
                video_id=video_id,
                ordinal=int(item["ordinal"]),
                timestamp_ms=item.get("timestamp_ms"),
                frame_kind=str(item.get("frame_kind") or "frame"),
                description=str(item["description"]),
                storage_key=item.get("storage_key"),
                alignment_confidence=float(item.get("alignment_confidence") or 0.0),
                provenance=str(item.get("provenance") or "fixture_data"),
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return rows

    async def list_for_asset(
        self,
        *,
        media_asset_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[MediaFrame]:
        result = await self._session.execute(
            select(MediaFrame)
            .where(
                MediaFrame.media_asset_id == media_asset_id,
                MediaFrame.workspace_id == workspace_id,
            )
            .order_by(MediaFrame.ordinal.asc())
        )
        return list(result.scalars().all())

    async def delete_for_video(
        self,
        *,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> int:
        result = await self._session.execute(
            delete(MediaFrame).where(
                MediaFrame.video_id == video_id,
                MediaFrame.workspace_id == workspace_id,
            )
        )
        await self._session.flush()
        return int(result.rowcount or 0)
