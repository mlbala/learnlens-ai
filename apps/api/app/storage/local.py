"""Local filesystem mock for private transcript blobs (dev/test)."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from app.storage.base import StoredObject

logger = logging.getLogger(__name__)

_SAFE_KEY = re.compile(r"^[a-f0-9-]{36}/[a-f0-9]{64}_[a-f0-9]{16}\.bin$")


class LocalMockStorage:
    """
    Stores objects under a private directory with randomized keys.

    Layout: {root}/{workspace_uuid}/{content_hash}_{random}.bin
    Rejects path traversal and symlink escapes on read/write.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        *,
        workspace_id: str,
        data: bytes,
        content_hash: str,
        content_type: str = "text/plain; charset=utf-8",
    ) -> StoredObject:
        del content_type  # reserved for future bucket metadata
        ws = uuid.UUID(workspace_id)
        key = f"{ws}/{content_hash}_{uuid.uuid4().hex[:16]}.bin"
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Refuse to follow symlinks out of root.
        if path.is_symlink() or path.parent.is_symlink():
            msg = "Refusing to write through symlink"
            raise OSError(msg)
        path.write_bytes(data)
        logger.info(
            "storage_put",
            extra={
                "storage_key": key,
                "size_bytes": len(data),
                "content_hash": content_hash,
            },
        )
        return StoredObject(storage_key=key, content_hash=content_hash, size_bytes=len(data))

    def get_bytes(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        if not path.is_file() or path.is_symlink():
            raise KeyError(storage_key)
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        try:
            path = self._resolve(storage_key)
        except ValueError:
            return
        if path.is_file() and not path.is_symlink():
            path.unlink(missing_ok=True)

    def _resolve(self, storage_key: str) -> Path:
        if not _SAFE_KEY.match(storage_key):
            msg = "Invalid storage key"
            raise ValueError(msg)
        candidate = (self._root / storage_key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            msg = "Path traversal rejected"
            raise ValueError(msg) from exc
        return candidate
