"""Storage adapter factory — local mock now; future private bucket seam."""

from __future__ import annotations

from pathlib import Path

from app.core.settings import Settings
from app.storage.base import StorageAdapter
from app.storage.local import LocalMockStorage

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _resolve_root(path_str: str) -> Path:
    root = Path(path_str)
    if not root.is_absolute():
        root = (_REPO_ROOT / root).resolve()
    return root


def get_storage_adapter(settings: Settings) -> StorageAdapter:
    """
    Return the configured storage adapter.

    `TRANSCRIPT_STORAGE_BACKEND=local` (default) uses a private directory.
    A future `s3` / `gcs` backend can plug in without changing callers.
    """
    backend = settings.transcript_storage_backend.strip().lower()
    if backend in {"local", "mock", "filesystem"}:
        return LocalMockStorage(_resolve_root(settings.transcript_storage_path))
    msg = f"Unsupported transcript storage backend: {backend}"
    raise RuntimeError(msg)


def get_media_storage_adapter(settings: Settings) -> StorageAdapter:
    """Private storage for authorized media uploads (separate from YouTube metadata)."""
    backend = settings.transcript_storage_backend.strip().lower()
    if backend in {"local", "mock", "filesystem"}:
        return LocalMockStorage(_resolve_root(settings.media_storage_path))
    msg = f"Unsupported media storage backend: {backend}"
    raise RuntimeError(msg)
