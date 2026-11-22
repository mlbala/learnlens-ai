"""Durable Gemini lesson history — Neon is the only copy.

Stores the public watch URL as a lesson row plus ordered transcript passages.
Does not download YouTube media or write object storage. Trimming a lesson
also deletes its outside-search rows and both origins of its Qdrant points.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.models import (
    Chapter,
    ChatMessage,
    ChatThread,
    ExternalEvidence,
    MessageCitation,
    SourceAsset,
    TranscriptSegment,
    Video,
    Workspace,
)
from app.domain.youtube_url import YoutubeUrlError, YoutubeUrlKind, parse_youtube_url
from app.services.lesson_cache import (
    LessonBodyCache,
    cache_delete_prefix,
    cache_get,
    cache_put,
    lesson_body_from_rows,
    lesson_body_key,
    lesson_body_prefix,
    segments_from_body,
)

SOURCE_KIND_GEMINI_YOUTUBE = "gemini_youtube"
EVIDENCE_ORIGIN_VIDEO_TRANSCRIPT = "video_transcript"
EVIDENCE_PROVIDER_GEMINI_YOUTUBE = "gemini_youtube"
LESSON_NOT_IN_WORKSPACE = "This lesson is not in this workspace."
DEFAULT_LEARNING_HISTORY_LIMIT = 10
MIN_LEARNING_HISTORY_LIMIT = 1
MAX_LEARNING_HISTORY_LIMIT = 100
_MAX_PASSAGES = 200
_BLANK_LINES = re.compile(r"\n\s*\n")

logger = logging.getLogger(__name__)


class LessonHistoryError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _summary_and_points(video: Video) -> tuple[str, list[str]]:
    meta = video.metadata_json if isinstance(video.metadata_json, dict) else {}
    lesson = meta.get("gemini_lesson") if isinstance(meta.get("gemini_lesson"), dict) else {}
    summary = str(lesson.get("summary") or "")
    raw_points = lesson.get("key_points") if isinstance(lesson.get("key_points"), list) else []
    points = [str(point) for point in raw_points if str(point).strip()]
    return summary, points


def passage_hash(text: str) -> str:
    """Hash of one passage's text. Timestamps are not part of the digest."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_transcript(transcript: str) -> list[str]:
    """Ordered passages. Blank lines first, then single lines. No invented times."""
    text = transcript.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    parts = [part.strip() for part in _BLANK_LINES.split(text) if part.strip()]
    if len(parts) == 1 and "\n" in parts[0]:
        parts = [part.strip() for part in parts[0].split("\n") if part.strip()]
    if len(parts) > _MAX_PASSAGES:
        head = parts[: _MAX_PASSAGES - 1]
        tail = "\n\n".join(parts[_MAX_PASSAGES - 1 :])
        parts = [*head, tail]
    return parts


class LessonHistoryService:
    def __init__(self, session: AsyncSession, cache: LessonBodyCache | None = None) -> None:
        self._session = session
        self._cache = cache

    async def get_limit(self, workspace_id: uuid.UUID) -> int:
        workspace = await self._workspace(workspace_id)
        return int(workspace.learning_history_limit)

    async def set_limit(self, workspace_id: uuid.UUID, limit: int) -> int:
        if limit < MIN_LEARNING_HISTORY_LIMIT or limit > MAX_LEARNING_HISTORY_LIMIT:
            raise LessonHistoryError(
                422,
                "INVALID_HISTORY_LIMIT",
                "Learning history limit must be an integer from 1 to 100.",
            )
        workspace = await self._workspace(workspace_id)
        workspace.learning_history_limit = limit
        await self._session.flush()
        await self.trim(workspace_id)
        return limit

    async def list_lessons(self, workspace_id: uuid.UUID) -> list[Video]:
        return await self._gemini_lessons(workspace_id)

    async def save_lesson(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        youtube_video_id: str,
        title: str,
        channel_title: str | None,
        summary: str,
        key_points: list[str],
        transcript: str,
        source_url: str,
    ) -> tuple[Video, list[TranscriptSegment], bool]:
        canonical = self._canonical_watch_url(source_url, youtube_video_id)
        passages = split_transcript(transcript)
        if not passages:
            raise LessonHistoryError(
                422,
                "EMPTY_TRANSCRIPT",
                "A lesson transcript is required before it can be saved.",
            )
        points = [point.strip() for point in key_points if point and point.strip()][:8]
        summary_text = summary.strip()
        cleaned_channel = None
        if channel_title and channel_title.strip():
            cleaned_channel = channel_title.strip()[:300]
        video, created = await self._upsert_video(
            workspace_id=workspace_id,
            youtube_video_id=youtube_video_id,
            title=(title or youtube_video_id).strip()[:500],
            channel_title=cleaned_channel,
            source_url=canonical,
            summary=summary_text,
            key_points=points,
        )
        await self._write_passages(
            video=video,
            workspace_id=workspace_id,
            user_id=user_id,
            passages=passages,
            transcript=transcript.strip(),
        )
        video.last_opened_at = utcnow()
        await self._session.flush()
        self._forget_cache(workspace_id, video.id)
        await self.trim(workspace_id)
        # The saved row may have been kept; re-read so callers see the post-trim row.
        fresh = await self._video_in_workspace(video.id, workspace_id)
        if fresh is None:
            raise LessonHistoryError(
                500,
                "LESSON_NOT_KEPT",
                "The lesson could not be kept in history.",
            )
        kept = await self._segments_for_video(fresh.id, workspace_id)
        return fresh, kept, created

    async def open_lesson(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> tuple[Video, list[TranscriptSegment]]:
        video = await self._gemini_video(video_id, workspace_id)
        if video is None:
            raise LessonHistoryError(404, "LESSON_NOT_IN_WORKSPACE", LESSON_NOT_IN_WORKSPACE)
        video.last_opened_at = utcnow()
        await self._session.flush()
        await self.trim(workspace_id)
        fresh = await self._gemini_video(video_id, workspace_id)
        if fresh is None:
            raise LessonHistoryError(404, "LESSON_NOT_IN_WORKSPACE", LESSON_NOT_IN_WORKSPACE)
        segments = await self._load_segments(fresh)
        return fresh, segments

    async def get_lesson(
        self,
        *,
        workspace_id: uuid.UUID,
        video_id: uuid.UUID,
    ) -> tuple[Video, list[TranscriptSegment]]:
        video = await self._gemini_video(video_id, workspace_id)
        if video is None:
            raise LessonHistoryError(404, "LESSON_NOT_IN_WORKSPACE", LESSON_NOT_IN_WORKSPACE)
        segments = await self._load_segments(video)
        return video, segments

    async def trim(self, workspace_id: uuid.UUID) -> None:
        workspace = await self._workspace(workspace_id)
        limit = int(workspace.learning_history_limit)
        lessons = await self._gemini_lessons(workspace_id)
        stale = lessons[limit:]
        if not stale:
            return
        video_ids = [video.id for video in stale]
        for video_id in video_ids:
            self._forget_cache(workspace_id, video_id)
        await self._session.execute(
            delete(MessageCitation).where(
                MessageCitation.workspace_id == workspace_id,
                MessageCitation.video_id.in_(video_ids),
            )
        )
        await self._session.execute(
            delete(ExternalEvidence).where(
                ExternalEvidence.workspace_id == workspace_id,
                ExternalEvidence.video_id.in_(video_ids),
            )
        )
        thread_ids = select(ChatThread.id).where(
            ChatThread.workspace_id == workspace_id,
            ChatThread.scope_kind == "video",
            ChatThread.scope_id.in_(video_ids),
        )
        await self._session.execute(
            delete(ChatMessage).where(ChatMessage.thread_id.in_(thread_ids))
        )
        await self._session.execute(
            delete(ChatThread).where(
                ChatThread.workspace_id == workspace_id,
                ChatThread.scope_kind == "video",
                ChatThread.scope_id.in_(video_ids),
            )
        )
        self._delete_lesson_points(workspace_id, video_ids)
        await self._session.execute(
            update(Chapter)
            .where(Chapter.workspace_id == workspace_id, Chapter.video_id.in_(video_ids))
            .values(start_segment_id=None, end_segment_id=None)
        )
        await self._session.execute(
            delete(Chapter).where(
                Chapter.workspace_id == workspace_id,
                Chapter.video_id.in_(video_ids),
            )
        )
        await self._session.execute(
            delete(TranscriptSegment).where(
                TranscriptSegment.workspace_id == workspace_id,
                TranscriptSegment.video_id.in_(video_ids),
            )
        )
        await self._session.execute(
            delete(SourceAsset).where(
                SourceAsset.workspace_id == workspace_id,
                SourceAsset.video_id.in_(video_ids),
            )
        )
        await self._session.execute(
            delete(Video).where(Video.workspace_id == workspace_id, Video.id.in_(video_ids))
        )
        await self._session.flush()

    def _forget_cache(self, workspace_id: uuid.UUID, video_id: uuid.UUID) -> None:
        cache_delete_prefix(self._cache, lesson_body_prefix(workspace_id, video_id))

    async def _load_segments(self, video: Video) -> list[TranscriptSegment]:
        asset = await self._gemini_asset(video.id, video.workspace_id)
        summary, points = _summary_and_points(video)
        if asset is not None and asset.content_hash:
            key = lesson_body_key(video.workspace_id, video.id, asset.content_hash)
            cached = cache_get(self._cache, key)
            if cached is not None:
                return segments_from_body(cached)  # type: ignore[return-value]
            rows = await self._segments_for_video(video.id, video.workspace_id)
            cache_put(self._cache, key, lesson_body_from_rows(summary, points, rows))
            return rows
        return await self._segments_for_video(video.id, video.workspace_id)

    def _delete_lesson_points(self, workspace_id: uuid.UUID, video_ids: list[uuid.UUID]) -> None:
        """Drop both evidence origins for each trimmed lesson. Limits stay unchanged."""
        try:
            from app.core.settings import get_settings
            from app.retrieval.factory import build_vector_store
            from app.retrieval.profile import active_embedding_profile

            settings = get_settings()
            profile = active_embedding_profile(settings)
            store = build_vector_store(settings)
            collection = store.ensure_collection(
                profile_id=profile.profile_id,
                dimensions=profile.dimensions,
            )
            for video_id in video_ids:
                store.delete_by_video(
                    collection=collection,
                    workspace_id=workspace_id,
                    video_id=video_id,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "lesson_index_delete_failed",
                extra={
                    "workspace_id": str(workspace_id),
                    "video_count": len(video_ids),
                    "error_type": type(exc).__name__,
                },
            )

    async def _workspace(self, workspace_id: uuid.UUID) -> Workspace:
        workspace = await self._session.get(Workspace, workspace_id)
        if workspace is None:
            raise LessonHistoryError(404, "NOT_FOUND", "Resource not found.")
        return workspace

    async def _gemini_lessons(self, workspace_id: uuid.UUID) -> list[Video]:
        result = await self._session.execute(
            select(Video)
            .join(SourceAsset, SourceAsset.video_id == Video.id)
            .where(
                Video.workspace_id == workspace_id,
                SourceAsset.workspace_id == workspace_id,
                SourceAsset.source_kind == SOURCE_KIND_GEMINI_YOUTUBE,
            )
            .order_by(Video.last_opened_at.desc(), Video.id.desc())
        )
        ordered: list[Video] = []
        seen: set[uuid.UUID] = set()
        for video in result.scalars().all():
            if video.id in seen:
                continue
            seen.add(video.id)
            ordered.append(video)
        return ordered

    async def _video_in_workspace(
        self,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Video | None:
        result = await self._session.execute(
            select(Video).where(Video.id == video_id, Video.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def _gemini_video(
        self,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Video | None:
        video = await self._video_in_workspace(video_id, workspace_id)
        if video is None:
            return None
        asset = await self._gemini_asset(video.id, workspace_id)
        if asset is None:
            return None
        return video

    async def _gemini_asset(
        self,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> SourceAsset | None:
        result = await self._session.execute(
            select(SourceAsset)
            .where(
                SourceAsset.video_id == video_id,
                SourceAsset.workspace_id == workspace_id,
                SourceAsset.source_kind == SOURCE_KIND_GEMINI_YOUTUBE,
            )
            .order_by(SourceAsset.source_revision.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _segments_for_video(
        self,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[TranscriptSegment]:
        asset = await self._gemini_asset(video_id, workspace_id)
        if asset is None:
            return []
        result = await self._session.execute(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.asset_id == asset.id,
                TranscriptSegment.workspace_id == workspace_id,
                TranscriptSegment.video_id == video_id,
            )
            .order_by(TranscriptSegment.ordinal.asc())
        )
        return list(result.scalars().all())

    async def _upsert_video(
        self,
        *,
        workspace_id: uuid.UUID,
        youtube_video_id: str,
        title: str,
        channel_title: str | None,
        source_url: str,
        summary: str,
        key_points: list[str],
    ) -> tuple[Video, bool]:
        result = await self._session.execute(
            select(Video).where(
                Video.workspace_id == workspace_id,
                Video.youtube_video_id == youtube_video_id,
            )
        )
        existing = result.scalar_one_or_none()
        lesson_meta = {"summary": summary, "key_points": key_points}
        if existing is None:
            video = Video(
                workspace_id=workspace_id,
                youtube_video_id=youtube_video_id,
                title=title,
                channel_title=channel_title,
                source_url=source_url,
                status="ready",
                metadata_json={
                    "gemini_lesson": lesson_meta,
                    "transcript_access": True,
                    "coverage": "ready",
                    "fixture_data": False,
                },
                last_opened_at=datetime.now(UTC),
            )
            self._session.add(video)
            await self._session.flush()
            return video, True

        meta = dict(existing.metadata_json or {})
        meta["gemini_lesson"] = lesson_meta
        meta["transcript_access"] = True
        meta["coverage"] = "ready"
        meta["fixture_data"] = False
        existing.title = title or existing.title
        if channel_title:
            existing.channel_title = channel_title
        existing.source_url = source_url
        existing.status = "ready"
        existing.metadata_json = meta
        await self._session.flush()
        return existing, False

    async def _write_passages(
        self,
        *,
        video: Video,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        passages: list[str],
        transcript: str,
    ) -> list[TranscriptSegment]:
        digest = passage_hash(transcript)
        asset = await self._gemini_asset(video.id, workspace_id)
        if asset is None:
            asset = SourceAsset(
                video_id=video.id,
                workspace_id=workspace_id,
                source_kind=SOURCE_KIND_GEMINI_YOUTUBE,
                storage_key=f"gemini-youtube/{workspace_id}/{video.youtube_video_id}",
                content_hash=digest,
                rights_attested_at=None,
                uploaded_by=user_id,
                timecode_quality="none",
                source_revision=1,
            )
            self._session.add(asset)
            await self._session.flush()
            return await self._insert_segments(asset, video.id, workspace_id, passages)

        existing = await self._segments_for_video(video.id, workspace_id)
        same = len(existing) == len(passages) and all(
            row.text == text for row, text in zip(existing, passages, strict=True)
        )
        if same:
            return existing

        self._forget_cache(workspace_id, video.id)
        asset.content_hash = digest
        asset.source_revision = int(asset.source_revision) + 1
        asset.timecode_quality = "none"
        await self._session.execute(
            delete(TranscriptSegment).where(
                TranscriptSegment.asset_id == asset.id,
                TranscriptSegment.workspace_id == workspace_id,
            )
        )
        await self._session.flush()
        return await self._insert_segments(asset, video.id, workspace_id, passages)

    async def _insert_segments(
        self,
        asset: SourceAsset,
        video_id: uuid.UUID,
        workspace_id: uuid.UUID,
        passages: list[str],
    ) -> list[TranscriptSegment]:
        rows: list[TranscriptSegment] = []
        for index, text in enumerate(passages, start=1):
            row = TranscriptSegment(
                asset_id=asset.id,
                video_id=video_id,
                workspace_id=workspace_id,
                ordinal=index,
                text=text,
                start_ms=None,
                end_ms=None,
                speaker=None,
                content_hash=passage_hash(text),
                evidence_origin=EVIDENCE_ORIGIN_VIDEO_TRANSCRIPT,
                evidence_provider=EVIDENCE_PROVIDER_GEMINI_YOUTUBE,
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return rows

    def _canonical_watch_url(self, source_url: str, youtube_video_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", youtube_video_id):
            raise LessonHistoryError(
                422,
                "INVALID_VIDEO_ID",
                "A public 11-character YouTube video id is required.",
            )
        try:
            parsed = parse_youtube_url(source_url)
        except YoutubeUrlError as exc:
            raise LessonHistoryError(422, exc.code, str(exc)) from exc
        if parsed.kind != YoutubeUrlKind.VIDEO or parsed.video_id != youtube_video_id:
            raise LessonHistoryError(
                422,
                "VIDEO_URL_MISMATCH",
                "The source URL must be the public watch URL for this video.",
            )
        return parsed.canonical_url
