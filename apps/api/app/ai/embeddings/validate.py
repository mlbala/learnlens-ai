"""Embedding vector validation — dimension, finiteness."""

from __future__ import annotations

import math

from app.ai.errors import EmbeddingDimensionMismatch, ProviderResponseInvalid


def assert_vector(
    vector: list[float],
    *,
    expected_dimensions: int,
    provider: str,
) -> list[float]:
    if len(vector) != expected_dimensions:
        raise EmbeddingDimensionMismatch(
            (
                f"Embedding dimension mismatch: expected {expected_dimensions}, "
                f"got {len(vector)}. Reindex required before switching profiles."
            ),
            expected=expected_dimensions,
            actual=len(vector),
            provider=provider,
        )
    for value in vector:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ProviderResponseInvalid(
                "Embedding contained a non-numeric value.",
                provider=provider,
                details={"error_kind": "invalid_vector"},
            )
        if math.isnan(value) or math.isinf(value):
            raise ProviderResponseInvalid(
                "Embedding contained NaN or Inf.",
                provider=provider,
                details={"error_kind": "invalid_vector"},
            )
    return [float(v) for v in vector]
