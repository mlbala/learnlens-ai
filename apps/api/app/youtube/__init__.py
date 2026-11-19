"""YouTube Data API metadata adapters (official endpoints only; fake for offline)."""

from app.youtube.contracts import (
    PlaylistItemMeta,
    PlaylistMeta,
    VideoMeta,
    YoutubeMetadataClient,
)
from app.youtube.factory import build_youtube_metadata_client

__all__ = [
    "PlaylistItemMeta",
    "PlaylistMeta",
    "VideoMeta",
    "YoutubeMetadataClient",
    "build_youtube_metadata_client",
]
