"""YouTube metadata import — official/fake adapters only; never fetch user URLs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.models import Playlist, PlaylistItem, Video
from app.db.repositories.jobs import IngestionJobRepository
from app.db.repositories.playlists import PlaylistRepository
from app.db.repositories.videos import VideoRepository
from app.domain.youtube_url import (
    ParsedYoutubeUrl,
    YoutubeUrlError,
    YoutubeUrlKind,
    parse_youtube_url,
)
from app.youtube.contracts import (
    PlaylistItemMeta,
    VideoAvailability,
    VideoMeta,
    YoutubeMetadataClient,
)
from app.youtube.errors import (
    YoutubeAuthError,
    YoutubeConfigurationError,
    YoutubeMetadataError,
    YoutubeNotFound,
    YoutubeQuotaExceeded,
    YoutubeTemporarilyUnavailable,
)
from app.youtube.factory import build_youtube_metadata_client

# Honest source statuses after metadata-only import (never summarized/ready).
_SUMMARIZED_STATUSES = frozenset({"ready", "summarizing", "indexing"})


@dataclass(frozen=True, slots=True)
class ImportNotice:
    code: str
    message: str


@dataclass(slots=True)
class VideoImportResult:
    video: Video
    created: bool
    notices: list[ImportNotice]
    companion_playlist_id: str | None = None


@dataclass(slots=True)
class PlaylistImportResult:
    playlist: Playlist
    items: list[PlaylistItem]
    created: bool
    notices: list[ImportNotice]
    truncated: bool = False


def _status_for_availability(availability: VideoAvailability) -> str:
    if availability in {"private", "deleted", "unavailable"}:
        return "unavailable"
    # Public/unlisted metadata without transcript access.
    return "needs_transcript"


def _item_state(availability: VideoAvailability) -> str:
    if availability in {"private", "deleted", "unavailable"}:
        return "unavailable"
    return "needs_transcript"


def _video_metadata_json(meta: VideoMeta, *, coverage: str) -> dict[str, Any]:
    return {
        "coverage": coverage,
        "availability": meta.availability,
        "thumbnail_url": meta.thumbnail_url,
        "description_preview": meta.description_preview,
        "fixture_data": meta.fixture_data,
        "transcript_access": False,
        "source_note": (
            "A pasted public video URL does not grant transcript access. "
            "Upload a permitted transcript to summarize this video."
        ),
    }


class YoutubeImportService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        client: YoutubeMetadataClient | None = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._videos = VideoRepository(db)
        self._playlists = PlaylistRepository(db)
        self._jobs = IngestionJobRepository(db)
        self._client = client

    def _get_client(self) -> YoutubeMetadataClient:
        if self._client is not None:
            return self._client
        return build_youtube_metadata_client(self._settings)

    @staticmethod
    def parse_url(raw: str) -> ParsedYoutubeUrl:
        return parse_youtube_url(raw)

    def _idem_key(self, workspace_id: uuid.UUID, client_key: str) -> str:
        return f"{workspace_id}:{client_key.strip()[:96]}"

    async def _replay_idempotency(
        self,
        *,
        workspace_id: uuid.UUID,
        client_key: str | None,
        expected_type: Literal["video_import", "playlist_import"],
    ) -> uuid.UUID | None:
        if not client_key or not client_key.strip():
            return None
        job = await self._jobs.get_by_idempotency_key(self._idem_key(workspace_id, client_key))
        if job is None:
            return None
        if job.job_type != expected_type or job.workspace_id != workspace_id:
            raise YoutubeMetadataError(
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key was already used for a different import.",
            )
        return job.result_resource_id

    async def _record_idempotency(
        self,
        *,
        workspace_id: uuid.UUID,
        client_key: str | None,
        job_type: Literal["video_import", "playlist_import"],
        result_id: uuid.UUID,
        video_id: uuid.UUID | None = None,
    ) -> None:
        if not client_key or not client_key.strip():
            return
        existing = await self._jobs.get_by_idempotency_key(self._idem_key(workspace_id, client_key))
        if existing is not None:
            return
        await self._jobs.create_succeeded(
            workspace_id=workspace_id,
            job_type=job_type,
            idempotency_key=self._idem_key(workspace_id, client_key),
            result_resource_id=result_id,
            video_id=video_id,
        )

    async def import_video_url(
        self,
        *,
        workspace_id: uuid.UUID,
        youtube_url: str,
        idempotency_key: str | None = None,
    ) -> VideoImportResult:
        replay_id = await self._replay_idempotency(
            workspace_id=workspace_id,
            client_key=idempotency_key,
            expected_type="video_import",
        )
        if replay_id is not None:
            video = await self._videos.get_in_workspace(
                video_id=replay_id, workspace_id=workspace_id
            )
            if video is not None:
                return VideoImportResult(
                    video=video,
                    created=False,
                    notices=[
                        ImportNotice(
                            "IDEMPOTENT_REPLAY",
                            "Returned existing import for Idempotency-Key.",
                        ),
                        ImportNotice(
                            "SOURCE_TRANSCRIPT_REQUIRED",
                            "A pasted public video URL does not grant transcript access.",
                        ),
                    ],
                )

        try:
            parsed = parse_youtube_url(youtube_url)
        except YoutubeUrlError as exc:
            raise YoutubeMetadataError(exc.code, str(exc)) from exc

        if parsed.kind is not YoutubeUrlKind.VIDEO or not parsed.video_id:
            raise YoutubeMetadataError(
                "WRONG_URL_KIND",
                "Expected a video URL. Use the playlist import endpoint for playlists.",
            )

        client = self._get_client()
        meta = await client.get_video(parsed.video_id)
        status = _status_for_availability(meta.availability)
        coverage = "unavailable" if status == "unavailable" else "metadata_only"
        notices = [
            ImportNotice(
                "SOURCE_TRANSCRIPT_REQUIRED",
                "A pasted public video URL does not grant transcript access. "
                "Upload a permitted transcript to summarize this video.",
            )
        ]
        if parsed.has_companion_playlist:
            notices.append(
                ImportNotice(
                    "COMPANION_PLAYLIST",
                    "This watch URL also references a playlist. "
                    "Only the single video was imported; use playlist import explicitly "
                    f"for list={parsed.companion_playlist_id}.",
                )
            )
        if status == "unavailable":
            notices.append(
                ImportNotice(
                    "YOUTUBE_UNAVAILABLE",
                    "Video is private, deleted, or unavailable via the official API.",
                )
            )

        video, created = await self._videos.upsert_from_metadata(
            workspace_id=workspace_id,
            youtube_video_id=meta.youtube_video_id,
            title=meta.title or f"Unavailable video {meta.youtube_video_id}",
            channel_title=meta.channel_title,
            duration_seconds=meta.duration_seconds,
            source_url=parsed.canonical_url,
            status=status,
            metadata_json=_video_metadata_json(meta, coverage=coverage),
        )
        if video.status in _SUMMARIZED_STATUSES:
            # Hard invariant: metadata import must never claim summarized.
            video.status = "needs_transcript"
            await self._db.flush()

        await self._record_idempotency(
            workspace_id=workspace_id,
            client_key=idempotency_key,
            job_type="video_import",
            result_id=video.id,
            video_id=video.id,
        )
        return VideoImportResult(
            video=video,
            created=created,
            notices=notices,
            companion_playlist_id=parsed.companion_playlist_id,
        )

    async def _upsert_playlist_video(
        self,
        *,
        workspace_id: uuid.UUID,
        item: PlaylistItemMeta,
    ) -> Video | None:
        if item.availability in {"private", "deleted", "unavailable"}:
            # Persist a stub video only when we have a real youtube id (not missing_*).
            if item.youtube_video_id.startswith("missing_"):
                return None
            video, _ = await self._videos.upsert_from_metadata(
                workspace_id=workspace_id,
                youtube_video_id=item.youtube_video_id,
                title=item.title or f"Unavailable video {item.youtube_video_id}",
                channel_title=item.channel_title,
                duration_seconds=item.duration_seconds,
                source_url=f"https://www.youtube.com/watch?v={item.youtube_video_id}",
                status="unavailable",
                metadata_json={
                    "coverage": "unavailable",
                    "availability": item.availability,
                    "fixture_data": item.fixture_data,
                    "transcript_access": False,
                    "source_note": "Video unavailable via official API metadata.",
                },
            )
            return video

        video, _ = await self._videos.upsert_from_metadata(
            workspace_id=workspace_id,
            youtube_video_id=item.youtube_video_id,
            title=item.title or item.youtube_video_id,
            channel_title=item.channel_title,
            duration_seconds=item.duration_seconds,
            source_url=f"https://www.youtube.com/watch?v={item.youtube_video_id}",
            status="needs_transcript",
            metadata_json={
                "coverage": "metadata_only",
                "availability": item.availability,
                "fixture_data": item.fixture_data,
                "transcript_access": False,
                "source_note": (
                    "A pasted public video URL does not grant transcript access."
                ),
            },
        )
        return video

    async def import_playlist_url(
        self,
        *,
        workspace_id: uuid.UUID,
        youtube_url: str,
        idempotency_key: str | None = None,
    ) -> PlaylistImportResult:
        replay_id = await self._replay_idempotency(
            workspace_id=workspace_id,
            client_key=idempotency_key,
            expected_type="playlist_import",
        )
        if replay_id is not None:
            playlist = await self._playlists.get_in_workspace(
                playlist_id=replay_id, workspace_id=workspace_id
            )
            if playlist is not None:
                items = await self._playlists.list_items(playlist_id=playlist.id)
                return PlaylistImportResult(
                    playlist=playlist,
                    items=items,
                    created=False,
                    notices=[
                        ImportNotice(
                            "IDEMPOTENT_REPLAY",
                            "Returned existing import for Idempotency-Key.",
                        ),
                        ImportNotice(
                            "SOURCE_TRANSCRIPT_REQUIRED",
                            "Playlist metadata import does not grant transcript access.",
                        ),
                    ],
                )

        try:
            parsed = parse_youtube_url(youtube_url)
        except YoutubeUrlError as exc:
            raise YoutubeMetadataError(exc.code, str(exc)) from exc

        if parsed.kind is not YoutubeUrlKind.PLAYLIST or not parsed.playlist_id:
            raise YoutubeMetadataError(
                "WRONG_URL_KIND",
                "Expected a playlist URL. Use the video import endpoint for videos.",
            )

        client = self._get_client()
        page_size = min(max(self._settings.youtube_playlist_page_size, 1), 50)
        max_items = max(self._settings.youtube_playlist_max_items, 1)
        meta = await client.get_playlist(
            parsed.playlist_id,
            page_size=page_size,
            max_items=max_items,
        )

        notices = [
            ImportNotice(
                "SOURCE_TRANSCRIPT_REQUIRED",
                "Playlist metadata import does not grant transcript access for any item. "
                "Each video remains needs_transcript until a permitted transcript is attached.",
            )
        ]
        if meta.truncated:
            notices.append(
                ImportNotice(
                    "PLAYLIST_TRUNCATED",
                    f"Import stopped at configured max of {max_items} items.",
                )
            )

        existing = await self._playlists.get_by_youtube_id(
            workspace_id=workspace_id,
            youtube_playlist_id=meta.youtube_playlist_id,
        )
        created = existing is None
        playlist = await self._playlists.upsert(
            workspace_id=workspace_id,
            youtube_playlist_id=meta.youtube_playlist_id,
            title=meta.title,
            status="metadata_only",
            total_items=len(meta.items),
        )

        built_items: list[PlaylistItem] = []
        for item in meta.items:
            video = await self._upsert_playlist_video(workspace_id=workspace_id, item=item)
            built_items.append(
                PlaylistItem(
                    playlist_id=playlist.id,
                    video_id=video.id if video is not None else None,
                    playlist_position=item.playlist_position,
                    youtube_video_id=item.youtube_video_id,
                    state=_item_state(item.availability),
                )
            )
        await self._playlists.replace_items(playlist_id=playlist.id, items=built_items)
        items = await self._playlists.list_items(playlist_id=playlist.id)

        await self._record_idempotency(
            workspace_id=workspace_id,
            client_key=idempotency_key,
            job_type="playlist_import",
            result_id=playlist.id,
        )
        return PlaylistImportResult(
            playlist=playlist,
            items=items,
            created=created,
            notices=notices,
            truncated=meta.truncated,
        )


def map_youtube_error_to_http(exc: Exception) -> tuple[int, str, str]:
    """Return (status, code, message) for public API errors."""
    if isinstance(exc, YoutubeUrlError):
        return 422, exc.code, str(exc)
    if isinstance(exc, YoutubeMetadataError) and exc.code in {
        "INVALID_URL",
        "INVALID_HOST",
        "INVALID_VIDEO_ID",
        "INVALID_PLAYLIST_ID",
        "UNSUPPORTED_URL",
        "WRONG_URL_KIND",
    }:
        return 422, exc.code, exc.message
    if isinstance(exc, YoutubeMetadataError) and exc.code == "IDEMPOTENCY_CONFLICT":
        return 409, exc.code, exc.message
    if isinstance(exc, YoutubeNotFound):
        return 404, exc.code, exc.message
    if isinstance(exc, YoutubeQuotaExceeded):
        return 429, exc.code, exc.message
    if isinstance(exc, YoutubeAuthError | YoutubeConfigurationError):
        return 503, exc.code, exc.message
    if isinstance(exc, YoutubeTemporarilyUnavailable):
        return 503, exc.code, exc.message
    if isinstance(exc, YoutubeMetadataError):
        return 422, exc.code, exc.message
    return 500, "INTERNAL_ERROR", "Unexpected error."
