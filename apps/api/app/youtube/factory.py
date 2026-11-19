"""Build YouTube metadata clients from settings (fake by default)."""

from __future__ import annotations

from app.core.settings import Settings
from app.youtube.api_client import YoutubeDataApiClient
from app.youtube.contracts import YoutubeMetadataClient
from app.youtube.errors import YoutubeConfigurationError
from app.youtube.fake import FakeYoutubeMetadataClient


def build_youtube_metadata_client(settings: Settings) -> YoutubeMetadataClient:
    provider = (settings.youtube_metadata_provider or "fake").strip().lower()
    if provider == "fake":
        return FakeYoutubeMetadataClient()
    if provider in {"youtube", "youtube_data_api", "official"}:
        if not settings.youtube_api_key.strip():
            raise YoutubeConfigurationError(
                "YOUTUBE_API_KEY is required when YOUTUBE_METADATA_PROVIDER is official."
            )
        return YoutubeDataApiClient(
            api_key=settings.youtube_api_key,
            timeout_seconds=float(settings.youtube_request_timeout_seconds),
            max_retries=settings.youtube_max_retries,
            cache_ttl_seconds=float(settings.youtube_metadata_cache_ttl_seconds),
        )
    raise YoutubeConfigurationError(f"Unsupported YouTube metadata provider: {provider!r}")
