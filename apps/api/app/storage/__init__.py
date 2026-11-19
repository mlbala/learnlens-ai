"""Private object storage adapters (local mock now; bucket later)."""

from app.storage.base import StorageAdapter, StoredObject
from app.storage.factory import get_storage_adapter

__all__ = ["StoredObject", "StorageAdapter", "get_storage_adapter"]
