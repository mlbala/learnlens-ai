"""Mocked embedding adapters + dimension mismatch — no paid calls."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.ai.embeddings.gemini_adapter import GeminiEmbeddingAdapter
from app.ai.embeddings.openai_adapter import OpenAIEmbeddingAdapter
from app.ai.errors import EmbeddingDimensionMismatch, ProviderResponseInvalid

from ai_helpers import FakeHTTPStatusError


@pytest.mark.asyncio
async def test_openai_embeddings_validate_dimensions() -> None:
    vector = [0.1] * 8
    create = AsyncMock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=vector)],
        )
    )
    client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    adapter = OpenAIEmbeddingAdapter(
        api_key="sk", model="allowlisted-embed", dimensions=8, client=client
    )
    out = await adapter.embed_query("fixture")
    assert out == vector


@pytest.mark.asyncio
async def test_openai_embeddings_dimension_mismatch() -> None:
    create = AsyncMock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3])],
        )
    )
    client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    adapter = OpenAIEmbeddingAdapter(
        api_key="sk", model="allowlisted-embed", dimensions=8, client=client, max_retries=0
    )
    with pytest.raises(EmbeddingDimensionMismatch) as excinfo:
        await adapter.embed_query("fixture")
    assert excinfo.value.expected == 8
    assert excinfo.value.actual == 3
    assert excinfo.value.details["reindex_required"] is True


@pytest.mark.asyncio
async def test_openai_embeddings_reject_nan() -> None:
    create = AsyncMock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[float("nan"), 0.1])],
        )
    )
    client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    adapter = OpenAIEmbeddingAdapter(
        api_key="sk", model="m", dimensions=2, client=client, max_retries=0
    )
    with pytest.raises(ProviderResponseInvalid):
        await adapter.embed_query("fixture")


@pytest.mark.asyncio
async def test_gemini_embeddings_ok() -> None:
    embed = AsyncMock(
        return_value=SimpleNamespace(embedding=SimpleNamespace(values=[0.2, 0.3, 0.4, 0.5]))
    )
    client = SimpleNamespace(models=SimpleNamespace(embed_content=embed))
    adapter = GeminiEmbeddingAdapter(
        api_key="gem", model="allowlisted-embed", dimensions=4, client=client
    )
    out = await adapter.embed_documents(["a", "b"])
    assert len(out) == 2
    assert out[0] == [0.2, 0.3, 0.4, 0.5]


@pytest.mark.asyncio
async def test_openai_embeddings_401() -> None:
    from app.ai.errors import ProviderConfigurationError

    create = AsyncMock(side_effect=FakeHTTPStatusError(401))
    client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    adapter = OpenAIEmbeddingAdapter(
        api_key="sk", model="m", dimensions=4, client=client, max_retries=0
    )
    with pytest.raises(ProviderConfigurationError):
        await adapter.embed_query("fixture")
