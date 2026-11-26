"""Qdrant collection setup runs once per process, and again after a failure."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from app.core.settings import Settings
from app.retrieval import factory, qdrant_store
from app.retrieval.contracts import DENSE_VECTOR_NAME
from app.retrieval.errors import VectorStoreUnavailable


class RecordingClient:
    def __init__(self, **_: Any) -> None:
        self.calls: list[str] = []
        self.fail_count = False

    def collection_exists(self, name: str) -> bool:
        self.calls.append("exists")
        return True

    def get_collection(self, name: str) -> Any:
        self.calls.append("get")
        vectors = {DENSE_VECTOR_NAME: SimpleNamespace(size=8)}
        return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=vectors)))

    def create_payload_index(self, **_: Any) -> None:
        self.calls.append("index")

    def count(self, **_: Any) -> Any:
        self.calls.append("count")
        if self.fail_count:
            raise RuntimeError("cluster suspended")
        return SimpleNamespace(count=3)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> qdrant_store.QdrantCloudStore:
    qdrant_store.reset_ready_collections()
    monkeypatch.setattr(qdrant_store, "QdrantClient", RecordingClient)
    yield qdrant_store.QdrantCloudStore(url="https://qdrant.test", api_key="k")
    qdrant_store.reset_ready_collections()


def test_setup_runs_once_for_the_same_collection(store: qdrant_store.QdrantCloudStore) -> None:
    client: RecordingClient = store._client  # type: ignore[assignment]
    first = store.ensure_collection(profile_id="p", dimensions=8)
    setup = list(client.calls)
    assert setup.count("index") == len(qdrant_store.PAYLOAD_INDEX_FIELDS)
    for _ in range(3):
        assert store.ensure_collection(profile_id="p", dimensions=8) == first
    assert client.calls == setup


def test_a_failed_call_makes_the_next_request_check_again(
    store: qdrant_store.QdrantCloudStore,
) -> None:
    client: RecordingClient = store._client  # type: ignore[assignment]
    name = store.ensure_collection(profile_id="p", dimensions=8)
    client.fail_count = True
    with pytest.raises(VectorStoreUnavailable):
        store.count_points(name)
    client.calls.clear()
    store.ensure_collection(profile_id="p", dimensions=8)
    assert "exists" in client.calls


def test_factory_reuses_one_client_per_cluster(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(qdrant_store, "QdrantClient", RecordingClient)
    factory.reset_qdrant_stores()
    qdrant = settings.model_copy(
        update={
            "qdrant_vector_store": "qdrant",
            "qdrant_url": "https://qdrant.test",
            "qdrant_api_key": "k",
        }
    )
    assert factory.build_vector_store(qdrant) is factory.build_vector_store(qdrant)
    other = qdrant.model_copy(update={"qdrant_api_key": "other"})
    assert factory.build_vector_store(other) is not factory.build_vector_store(qdrant)
    factory.reset_qdrant_stores()
