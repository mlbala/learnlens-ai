"""Offline fake text/embedding adapters — zero credentials."""

from __future__ import annotations

import math

import pytest
from app.ai.embeddings.fake import FakeEmbeddingAdapter
from app.ai.factory import build_embedding_model, build_text_model
from app.ai.text.fake import FakeTextAdapter
from app.core.settings import Settings

from ai_helpers import GROUNDED_QA_SCHEMA, sample_request


@pytest.mark.asyncio
async def test_fake_text_returns_schema_valid_fixture() -> None:
    adapter = FakeTextAdapter()
    result = await adapter.generate_structured(sample_request())
    assert result.parsed["confidence_label"] == "supported"
    assert result.usage.provider == "fake"
    assert result.usage.tokens_estimated is True
    assert adapter.recorded[0].purpose == "grounded_qa"
    assert "seg_fixture_01" in adapter.recorded[0].evidence_ids


@pytest.mark.asyncio
async def test_fake_embeddings_deterministic_and_normalized() -> None:
    adapter = FakeEmbeddingAdapter(dimensions=64)
    a = await adapter.embed_query("fixture alpha")
    b = await adapter.embed_query("fixture alpha")
    c = await adapter.embed_query("fixture beta")
    assert a == b
    assert a != c
    assert len(a) == 64
    assert math.isclose(math.sqrt(sum(v * v for v in a)), 1.0, rel_tol=1e-5)


def test_factory_builds_fake_without_keys(settings: Settings) -> None:
    text = build_text_model(settings)
    embed = build_embedding_model(settings)
    assert text.provider == "fake"
    assert embed.provider == "fake"
    assert embed.dimensions == 64


@pytest.mark.asyncio
async def test_fake_rejects_mismatched_schema() -> None:
    adapter = FakeTextAdapter()
    bad_schema = {
        "type": "object",
        "required": ["totally_missing_field"],
        "properties": {"totally_missing_field": {"type": "string"}},
    }
    with pytest.raises(Exception) as excinfo:
        await adapter.generate_structured(sample_request(response_schema=bad_schema))
    assert "PROVIDER_RESPONSE_INVALID" == excinfo.value.code  # type: ignore[attr-defined]


def test_grounded_schema_constant_shape() -> None:
    assert set(GROUNDED_QA_SCHEMA["required"]) == {
        "answer",
        "claims",
        "unsupported",
        "confidence_label",
    }
