"""Provider-neutral YouTube metadata contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

VideoAvailability = Literal["public", "unlisted", "private", "unavailable", "deleted"]


@dataclass(frozen=True, slots=True)
class VideoMeta:
    youtube_video_id: str
    title: str
    channel_title: str | None
    duration_seconds: int | None
    availability: VideoAvailability
    thumbnail_url: str | None = None
    description_preview: str | None = None
    fixture_data: bool = False
    raw_snippet: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class PlaylistItemMeta:
    youtube_video_id: str
    playlist_position: int  # 0-based position within the playlist
    title: str | None
    availability: VideoAvailability
    channel_title: str | None = None
    duration_seconds: int | None = None
    fixture_data: bool = False


@dataclass(frozen=True, slots=True)
class PlaylistMeta:
    youtube_playlist_id: str
    title: str
    channel_title: str | None
    items: tuple[PlaylistItemMeta, ...]
    truncated: bool = False
    total_reported: int | None = None
    fixture_data: bool = False


@runtime_checkable
class YoutubeMetadataClient(Protocol):
    """Fetch metadata via constructed official endpoints or offline fixtures."""

    async def get_video(self, youtube_video_id: str) -> VideoMeta: ...

    async def get_playlist(
        self,
        youtube_playlist_id: str,
        *,
        page_size: int = 50,
        max_items: int = 200,
    ) -> PlaylistMeta: ...
