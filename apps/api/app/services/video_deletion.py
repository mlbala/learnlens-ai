"""Workspace-scoped video deletion — removes media, frames, indexes, storage."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policies.audit_policy import AuditRecord, get_audit_policy
from app.core.settings import Settings
from app.db.models import (
    Chapter,
    IndexManifest,
    MediaAsset,
    MediaFrame,
    SourceAsset,
    TranscriptSegment,
    Video,
)
from app.db.repositories import VideoRepository
from app.db.repositories.audit import AuditEventRepository
from app.retrieval.factory import build_vector_store
from app.retrieval.profile import active_embedding_profile
from app.storage.factory import get_media_storage_adapter, get_storage_adapter

logger = logging.getLogger(__name__)


class VideoDeletionError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class VideoDeletionResult:
    video_id: uuid.UUID
    media_removed: int
    frames_removed: int
    storage_keys_removed: int
    index_points_removed: int


class VideoDeletionService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._videos = VideoRepository(session)
        self._transcript_storage = get_storage_adapter(settings)
        self._media_storage = get_media_storage_adapter(settings)

    async def delete_video(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> VideoDeletionResult:
        video = await self._videos.get_in_workspace(
            video_id=video_id,
            workspace_id=workspace_id,
        )
        if video is None:
            get_audit_policy().record(
                AuditRecord(
                    action="authorization_denied",
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    resource_type="video",
                    resource_id=str(video_id),
                    metadata={"reason": "cross_tenant_or_missing", "action": "delete"},
                )
            )
            raise VideoDeletionError(404, "NOT_FOUND", "Resource not found.")

        media_rows = list(
            (
                await self._session.execute(
                    select(MediaAsset).where(
                        MediaAsset.video_id == video_id,
                        MediaAsset.workspace_id == workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        frame_rows = list(
            (
                await self._session.execute(
                    select(MediaFrame).where(
                        MediaFrame.video_id == video_id,
                        MediaFrame.workspace_id == workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        source_rows = list(
            (
                await self._session.execute(
                    select(SourceAsset).where(
                        SourceAsset.video_id == video_id,
                        SourceAsset.workspace_id == workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        storage_keys: list[tuple[str, str]] = []
        for m in media_rows:
            storage_keys.append(("media", m.storage_key))
        for f in frame_rows:
            if f.storage_key:
                storage_keys.append(("media", f.storage_key))
        for s in source_rows:
            if s.source_kind == "licensed_media":
                storage_keys.append(("media", s.storage_key))
            else:
                storage_keys.append(("transcript", s.storage_key))

        index_removed = 0
        try:
            profile = active_embedding_profile(self._settings)
            store = build_vector_store(self._settings)
            collection = store.ensure_collection(
                profile_id=profile.profile_id,
                dimensions=profile.dimensions,
            )
            index_removed = store.delete_by_video(
                collection=collection,
                workspace_id=workspace_id,
                video_id=video_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "video_index_delete_failed",
                extra={
                    "video_id": str(video_id),
                    "workspace_id": str(workspace_id),
                    "error_type": type(exc).__name__,
                },
            )

        await self._session.execute(
            delete(MediaFrame).where(
                MediaFrame.video_id == video_id,
                MediaFrame.workspace_id == workspace_id,
            )
        )
        await self._session.execute(
            delete(MediaAsset).where(
                MediaAsset.video_id == video_id,
                MediaAsset.workspace_id == workspace_id,
            )
        )
        await self._session.execute(
            delete(Chapter).where(
                Chapter.video_id == video_id,
                Chapter.workspace_id == workspace_id,
            )
        )
        await self._session.execute(
            delete(TranscriptSegment).where(
                TranscriptSegment.video_id == video_id,
                TranscriptSegment.workspace_id == workspace_id,
            )
        )
        await self._session.execute(
            delete(SourceAsset).where(
                SourceAsset.video_id == video_id,
                SourceAsset.workspace_id == workspace_id,
            )
        )
        await self._session.execute(
            delete(IndexManifest).where(
                IndexManifest.video_id == video_id,
                IndexManifest.workspace_id == workspace_id,
            )
        )

        video.status = "deleted"
        await self._session.flush()
        await self._session.execute(
            delete(Video).where(
                Video.id == video_id,
                Video.workspace_id == workspace_id,
            )
        )
        await self._session.flush()

        keys_removed = 0
        seen: set[str] = set()
        for kind, key in storage_keys:
            if key in seen:
                continue
            seen.add(key)
            try:
                if kind == "media":
                    self._media_storage.delete(key)
                else:
                    self._transcript_storage.delete(key)
                keys_removed += 1
            except Exception:  # noqa: BLE001
                logger.warning(
                    "storage_delete_failed",
                    extra={"storage_key": key, "kind": kind},
                )

        audit_meta = {
            "media_removed": len(media_rows),
            "frames_removed": len(frame_rows),
            "storage_keys_removed": keys_removed,
            "index_points_removed": index_removed,
        }
        get_audit_policy().record(
            AuditRecord(
                action="video_deleted",
                workspace_id=workspace_id,
                actor_user_id=user_id,
                resource_type="video",
                resource_id=str(video_id),
                metadata=audit_meta,
            )
        )
        await AuditEventRepository(self._session).create(
            action="video_deleted",
            workspace_id=workspace_id,
            actor_user_id=user_id,
            resource_type="video",
            resource_id=str(video_id),
            metadata=audit_meta,
            summary="Video and authorized media purged",
        )

        return VideoDeletionResult(
            video_id=video_id,
            media_removed=len(media_rows),
            frames_removed=len(frame_rows),
            storage_keys_removed=keys_removed,
            index_points_removed=index_removed,
        )
