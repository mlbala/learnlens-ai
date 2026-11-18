"""Deterministic offline embeddings — fixed dimensions, no network."""

from __future__ import annotations

import hashlib
import math
import struct

from app.ai.allowlist import embedding_profile_id
from app.ai.contracts import ModelCapabilities
from app.ai.embeddings.validate import assert_vector


class FakeEmbeddingAdapter:
    provider = "fake"

    def __init__(self, *, model: str = "fake-embed-v1", dimensions: int = 64) -> None:
        self.model = model
        self._dimensions = dimensions
        self.profile_id = embedding_profile_id(self.provider, model, dimensions)
        self.capabilities = ModelCapabilities(
            supports_json_schema=False,
            supports_stream=False,
            supports_vision=False,
            supports_batch=True,
            max_context_tokens=8_192,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        seed = digest
        while len(values) < self._dimensions:
            for i in range(0, len(seed) - 3, 4):
                (raw,) = struct.unpack_from(">I", seed, i)
                # Map to (-1, 1)
                values.append((raw / 0xFFFFFFFF) * 2.0 - 1.0)
                if len(values) >= self._dimensions:
                    break
            seed = hashlib.sha256(seed).digest()
        # L2-normalize for stable cosine behavior in tests
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        vector = [v / norm for v in values]
        return assert_vector(vector, expected_dimensions=self._dimensions, provider=self.provider)

    async def health(self) -> dict[str, str]:
        return {
            "status": "ok",
            "provider": self.provider,
            "model": self.model,
            "profile_id": self.profile_id,
        }
