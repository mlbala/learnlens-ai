"""Storage adapter protocol — private keys only; no public URLs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    storage_key: str
    content_hash: str
    size_bytes: int


class StorageAdapter(Protocol):
    def put_bytes(
        self,
        *,
        workspace_id: str,
        data: bytes,
        content_hash: str,
        content_type: str = "text/plain; charset=utf-8",
    ) -> StoredObject:
        """Persist bytes under a randomized key outside the public web root."""

    def get_bytes(self, storage_key: str) -> bytes:
        """Read private object bytes. Raises KeyError if missing."""

    def delete(self, storage_key: str) -> None:
        """Best-effort delete; missing keys are ignored."""
