"""Offline fake YouTube metadata client backed by marked fixture JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.youtube.contracts import PlaylistItemMeta, PlaylistMeta, VideoMeta
from app.youtube.errors import YoutubeNotFound

# fixtures/youtube at repo root: fake.py → youtube → app → api → apps → root
_DEFAULT_FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "youtube"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        msg = f"Fixture {path} must be a JSON object"
        raise TypeError(msg)
    return data


class FakeYoutubeMetadataClient:
    """Deterministic fixture client — never performs network I/O."""

    def __init__(
        self,
        *,
        fixtures_dir: Path | None = None,
        videos: dict[str, Any] | None = None,
        playlists: dict[str, Any] | None = None,
    ) -> None:
        root = fixtures_dir or _DEFAULT_FIXTURES
        if videos is None:
            videos_doc = _load_json(root / "videos.json")
            videos = dict(videos_doc.get("videos") or {})
        if playlists is None:
            playlists_doc = _load_json(root / "playlist_pages.json")
            playlists = dict(playlists_doc.get("playlists") or {})
        self._videos = videos
        self._playlists = playlists

    async def get_video(self, youtube_video_id: str) -> VideoMeta:
        row = self._videos.get(youtube_video_id)
        if row is None:
            raise YoutubeNotFound(f"Fixture video {youtube_video_id!r} not found.")
        availability = str(row.get("availability") or "unavailable")
        if availability in {"private", "deleted", "unavailable"}:
            # Still return a structured meta so import can persist unavailable state.
            return VideoMeta(
                youtube_video_id=youtube_video_id,
                title=str(row.get("title") or ""),
                channel_title=row.get("channel_title"),
                duration_seconds=row.get("duration_seconds"),
                availability=availability,  # type: ignore[arg-type]
                thumbnail_url=row.get("thumbnail_url"),
                description_preview=None,
                fixture_data=True,
            )
        return VideoMeta(
            youtube_video_id=youtube_video_id,
            title=str(row.get("title") or "Untitled fixture video"),
            channel_title=row.get("channel_title"),
            duration_seconds=row.get("duration_seconds"),
            availability=availability if availability in {"public", "unlisted"} else "public",  # type: ignore[arg-type]
            thumbnail_url=row.get("thumbnail_url"),
            description_preview=row.get("description_preview"),
            fixture_data=True,
            raw_snippet={"fixture_data": True},
        )

    async def get_playlist(
        self,
        youtube_playlist_id: str,
        *,
        page_size: int = 50,
        max_items: int = 200,
    ) -> PlaylistMeta:
        if page_size < 1 or page_size > 50:
            page_size = min(max(page_size, 1), 50)
        doc = self._playlists.get(youtube_playlist_id)
        if doc is None:
            raise YoutubeNotFound(f"Fixture playlist {youtube_playlist_id!r} not found.")

        pages = list(doc.get("pages") or [])
        collected: list[PlaylistItemMeta] = []
        truncated = False
        position = 0

        for page in pages:
            raw_items = list(page.get("items") or [])
            # Simulate API page_size by chunking each fixture page if needed.
            for start in range(0, len(raw_items), page_size):
                chunk = raw_items[start : start + page_size]
                for item in chunk:
                    if len(collected) >= max_items:
                        truncated = True
                        break
                    yt_id = str(item.get("youtube_video_id") or "")
                    availability = str(item.get("availability") or "unavailable")
                    collected.append(
                        PlaylistItemMeta(
                            youtube_video_id=yt_id,
                            playlist_position=position,
                            title=item.get("title"),
                            availability=availability,  # type: ignore[arg-type]
                            channel_title=item.get("channel_title"),
                            duration_seconds=item.get("duration_seconds"),
                            fixture_data=True,
                        )
                    )
                    position += 1
                if truncated:
                    break
            if truncated:
                break

        return PlaylistMeta(
            youtube_playlist_id=youtube_playlist_id,
            title=str(doc.get("title") or "Untitled fixture playlist"),
            channel_title=doc.get("channel_title"),
            items=tuple(collected),
            truncated=truncated,
            total_reported=doc.get("total_reported"),
            fixture_data=True,
        )


__all__ = ["FakeYoutubeMetadataClient"]
