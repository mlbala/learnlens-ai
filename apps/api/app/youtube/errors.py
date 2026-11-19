"""Structured YouTube metadata errors — never include API keys or raw payloads."""

from __future__ import annotations

from typing import Any


class YoutubeMetadataError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        super().__init__(message)


class YoutubeNotFound(YoutubeMetadataError):
    def __init__(self, message: str = "Video or playlist was not found.") -> None:
        super().__init__("YOUTUBE_NOT_FOUND", message, retryable=False)


class YoutubeUnavailable(YoutubeMetadataError):
    def __init__(self, message: str = "Video is private, deleted, or unavailable.") -> None:
        super().__init__("YOUTUBE_UNAVAILABLE", message, retryable=False)


class YoutubeQuotaExceeded(YoutubeMetadataError):
    def __init__(self, message: str = "YouTube API quota exceeded.") -> None:
        super().__init__("YOUTUBE_QUOTA_EXCEEDED", message, retryable=True)


class YoutubeAuthError(YoutubeMetadataError):
    def __init__(self, message: str = "YouTube API authorization failed.") -> None:
        super().__init__("YOUTUBE_AUTH_FAILED", message, retryable=False)


class YoutubeTemporarilyUnavailable(YoutubeMetadataError):
    def __init__(self, message: str = "YouTube API temporarily unavailable.") -> None:
        super().__init__("YOUTUBE_TEMPORARILY_UNAVAILABLE", message, retryable=True)


class YoutubeConfigurationError(YoutubeMetadataError):
    def __init__(self, message: str = "YouTube API is not configured.") -> None:
        super().__init__("YOUTUBE_NOT_CONFIGURED", message, retryable=False)
