"""Official YouTube Data API v3 metadata client — constructed googleapis URLs only."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.youtube.cache import TtlCache
from app.youtube.contracts import PlaylistItemMeta, PlaylistMeta, VideoAvailability, VideoMeta
from app.youtube.errors import (
    YoutubeAuthError,
    YoutubeConfigurationError,
    YoutubeNotFound,
    YoutubeQuotaExceeded,
    YoutubeTemporarilyUnavailable,
)

logger = logging.getLogger(__name__)

_API_ROOT = "https://www.googleapis.com/youtube/v3"
_ALLOWED_API_HOST = "www.googleapis.com"
_ISO8601_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def _parse_duration_seconds(iso: str | None) -> int | None:
    if not iso:
        return None
    match = _ISO8601_DURATION.fullmatch(iso)
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _map_privacy(status: dict[str, Any] | None) -> VideoAvailability:
    if not status:
        return "unavailable"
    privacy = str(status.get("privacyStatus") or "").lower()
    if privacy == "public":
        return "public"
    if privacy == "unlisted":
        return "unlisted"
    if privacy == "private":
        return "private"
    return "unavailable"


class YoutubeDataApiClient:
    """
    Calls only ``https://www.googleapis.com/youtube/v3/...``.

    Never fetches a user-supplied URL. Secrets stay server-side and are never logged.
    """

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise YoutubeConfigurationError("YOUTUBE_API_KEY is required for the live client.")
        self._api_key = key
        self._timeout = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._video_cache: TtlCache[VideoMeta] = TtlCache(ttl_seconds=cache_ttl_seconds)
        self._playlist_cache: TtlCache[PlaylistMeta] = TtlCache(ttl_seconds=cache_ttl_seconds)

    def _build_url(self, resource: str, params: dict[str, str]) -> str:
        if resource not in {"videos", "playlists", "playlistItems"}:
            msg = "Unsupported YouTube API resource"
            raise YoutubeConfigurationError(msg)
        query = urlencode({**params, "key": self._api_key})
        return f"{_API_ROOT}/{resource}?{query}"

    async def _get_json(self, url: str) -> dict[str, Any]:
        # Defense in depth: refuse any non-googleapis host even if misconstructed.
        if not url.startswith(f"https://{_ALLOWED_API_HOST}/"):
            raise YoutubeConfigurationError("Refusing outbound request to non-allowlisted host.")

        attempt = 0
        while True:
            try:
                return await asyncio.to_thread(self._get_json_sync, url)
            except YoutubeTemporarilyUnavailable:
                if attempt >= self._max_retries:
                    raise
                await asyncio.sleep(0.05 * (2**attempt))
                attempt += 1
            except YoutubeQuotaExceeded:
                raise

    def _get_json_sync(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "learnlens-ai/0.4"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:  # noqa: S310 — host allowlisted
                body = response.read()
        except HTTPError as exc:
            self._raise_http(exc)
        except URLError as exc:
            logger.info("youtube_api_transport_error", extra={"reason": type(exc).__name__})
            raise YoutubeTemporarilyUnavailable("YouTube API transport error.") from exc

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise YoutubeTemporarilyUnavailable("YouTube API returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise YoutubeTemporarilyUnavailable("YouTube API returned unexpected payload.")
        if "error" in payload:
            self._raise_api_error(payload["error"])
        return payload

    def _raise_http(self, exc: HTTPError) -> None:
        status = exc.code
        if status in {401, 403}:
            # Distinguish quota vs auth when possible from body.
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                err = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(err, dict):
                    self._raise_api_error(err)
            except Exception:  # noqa: BLE001 — fall through to generic auth
                pass
            raise YoutubeAuthError("YouTube API rejected the request.")
        if status == 404:
            raise YoutubeNotFound()
        if status == 429 or status >= 500:
            raise YoutubeTemporarilyUnavailable(f"YouTube API HTTP {status}.")
        raise YoutubeTemporarilyUnavailable(f"YouTube API HTTP {status}.")

    def _raise_api_error(self, error: dict[str, Any]) -> None:
        reasons: list[str] = []
        for item in error.get("errors") or []:
            if isinstance(item, dict) and item.get("reason"):
                reasons.append(str(item["reason"]))
        joined = ",".join(reasons).lower()
        if "quotaexceeded" in joined or "dailylimitexceeded" in joined:
            raise YoutubeQuotaExceeded()
        if "keyinvalid" in joined or "auth" in joined or error.get("code") in {401, 403}:
            raise YoutubeAuthError()
        raise YoutubeTemporarilyUnavailable("YouTube API error.")

    async def get_video(self, youtube_video_id: str) -> VideoMeta:
        cached = self._video_cache.get(youtube_video_id)
        if cached is not None:
            return cached

        url = self._build_url(
            "videos",
            {
                "part": "snippet,contentDetails,status",
                "id": youtube_video_id,
                "maxResults": "1",
            },
        )
        payload = await self._get_json(url)
        items = payload.get("items") or []
        if not items:
            meta = VideoMeta(
                youtube_video_id=youtube_video_id,
                title="",
                channel_title=None,
                duration_seconds=None,
                availability="unavailable",
            )
            self._video_cache.set(youtube_video_id, meta)
            return meta

        item = items[0]
        snippet = item.get("snippet") or {}
        status = item.get("status") or {}
        details = item.get("contentDetails") or {}
        availability = _map_privacy(status)
        thumbs = snippet.get("thumbnails") or {}
        thumb = None
        for key in ("medium", "high", "default"):
            node = thumbs.get(key)
            if isinstance(node, dict) and node.get("url"):
                # Only accept youtube thumbnail hosts — still never fetch them here.
                thumb_url = str(node["url"])
                if thumb_url.startswith("https://i.ytimg.com/") or thumb_url.startswith(
                    "https://yt3.ggpht.com/"
                ):
                    thumb = thumb_url
                break
        desc = snippet.get("description")
        preview = None
        if isinstance(desc, str) and desc.strip():
            preview = desc.strip()[:240]

        meta = VideoMeta(
            youtube_video_id=youtube_video_id,
            title=str(snippet.get("title") or ""),
            channel_title=snippet.get("channelTitle"),
            duration_seconds=_parse_duration_seconds(details.get("duration")),
            availability=availability,
            thumbnail_url=thumb,
            description_preview=preview,
            fixture_data=False,
            raw_snippet={"id": youtube_video_id},
        )
        if availability in {"private", "unavailable"} and not meta.title:
            # Treat empty private as unavailable for persistence.
            meta = VideoMeta(
                youtube_video_id=youtube_video_id,
                title="",
                channel_title=None,
                duration_seconds=None,
                availability="private" if availability == "private" else "unavailable",
                fixture_data=False,
            )
        self._video_cache.set(youtube_video_id, meta)
        return meta

    async def get_playlist(
        self,
        youtube_playlist_id: str,
        *,
        page_size: int = 50,
        max_items: int = 200,
    ) -> PlaylistMeta:
        page_size = min(max(int(page_size), 1), 50)
        max_items = max(int(max_items), 1)
        cache_key = f"{youtube_playlist_id}:{page_size}:{max_items}"
        cached = self._playlist_cache.get(cache_key)
        if cached is not None:
            return cached

        # Playlist header
        header_url = self._build_url(
            "playlists",
            {
                "part": "snippet,status",
                "id": youtube_playlist_id,
                "maxResults": "1",
            },
        )
        header = await self._get_json(header_url)
        header_items = header.get("items") or []
        if not header_items:
            raise YoutubeNotFound("Playlist was not found.")
        snippet = header_items[0].get("snippet") or {}
        title = str(snippet.get("title") or "")
        channel_title = snippet.get("channelTitle")

        collected: list[PlaylistItemMeta] = []
        truncated = False
        page_token: str | None = None
        position = 0
        total_reported: int | None = None

        while len(collected) < max_items:
            params: dict[str, str] = {
                "part": "snippet,status,contentDetails",
                "playlistId": youtube_playlist_id,
                "maxResults": str(page_size),
            }
            if page_token:
                params["pageToken"] = page_token
            page_url = self._build_url("playlistItems", params)
            page = await self._get_json(page_url)
            if total_reported is None:
                page_info = page.get("pageInfo") or {}
                total = page_info.get("totalResults")
                if isinstance(total, int):
                    total_reported = total

            for item in page.get("items") or []:
                if len(collected) >= max_items:
                    truncated = True
                    break
                content = item.get("contentDetails") or {}
                snip = item.get("snippet") or {}
                status = item.get("status") or {}
                resource_id = snip.get("resourceId")
                resource = resource_id if isinstance(resource_id, dict) else {}
                raw_id = content.get("videoId") or resource.get("videoId") or ""
                video_id = str(raw_id)
                if not video_id:
                    # Preserve positional slot for missing identity when API omits id.
                    video_id = f"missing_{position:04d}"
                    availability: VideoAvailability = "unavailable"
                    item_title = None
                else:
                    privacy = str(status.get("privacyStatus") or "").lower()
                    if privacy == "private":
                        availability = "private"
                    elif snip.get("title") in {"Deleted video", "Private video"}:
                        availability = (
                            "deleted" if snip.get("title") == "Deleted video" else "private"
                        )
                    elif privacy in {"public", "unlisted"}:
                        availability = privacy  # type: ignore[assignment]
                    else:
                        availability = "unavailable"
                    if availability in {"public", "unlisted"}:
                        item_title = snip.get("title")
                    else:
                        item_title = None

                collected.append(
                    PlaylistItemMeta(
                        youtube_video_id=video_id,
                        playlist_position=position,
                        title=item_title if isinstance(item_title, str) else None,
                        availability=availability,
                        channel_title=snip.get("videoOwnerChannelTitle"),
                        duration_seconds=None,
                        fixture_data=False,
                    )
                )
                position += 1

            page_token = page.get("nextPageToken")
            if truncated:
                break
            if not page_token:
                break

        if page_token and len(collected) >= max_items:
            truncated = True

        result = PlaylistMeta(
            youtube_playlist_id=youtube_playlist_id,
            title=title,
            channel_title=channel_title,
            items=tuple(collected),
            truncated=truncated,
            total_reported=total_reported,
            fixture_data=False,
        )
        self._playlist_cache.set(cache_key, result)
        return result
