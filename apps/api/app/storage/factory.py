"""Storage adapter factory — local mock now; future private bucket seam."""

from __future__ import annotations

from pathlib import Path

from app.core.settings import Settings
from app.storage.base import StorageAdapter
from app.storage.local import LocalMockStorage


def get_storage_adapter(settings: Settings) -> StorageAdapter:
    """
    Return the configured storage adapter.

    `TRANSCRIPT_STORAGE_BACKEND=local` (default) uses a private directory.
    A future `s3` / `gcs` backend can plug in without changing callers.
    """
    backend = settings.transcript_storage_backend.strip().lower()
    if backend in {"local", "mock", "filesystem"}:
        root = Path(settings.transcript_storage_path)
        if not root.is_absolute():
            # Resolve relative to repo root (parents: factory→storage→app→api→apps→repo)
            repo_root = Path(__file__).resolve().parents[4]
            root = (repo_root / root).resolve()
        return LocalMockStorage(root)
    msg = f"Unsupported transcript storage backend: {backend}"
    raise RuntimeError(msg)
