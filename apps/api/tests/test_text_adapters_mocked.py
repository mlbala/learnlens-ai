"""Mocked OpenAI / Gemini / DeepSeek text adapters — no paid network calls."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.ai.errors import (
    ProviderConfigurationError,
    ProviderRefused,
    ProviderResponseInvalid,
    ProviderTemporarilyUnavailable,
)
from app.ai.text.deepseek_adapter import DeepSeekTextAdapter
from app.ai.text.gemini_adapter import GeminiTextAdapter
from app.ai.text.openai_adapter import OpenAITextAdapter

from ai_helpers import (
    GROUNDED_QA_PAYLOAD,
    FakeHTTPStatusError,
    chat_completion_response,
    gemini_response,
    openai_response,
    sample_request,
)


@pytest.mark.asyncio
async def test_openai_text_parses_structured_json() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(return_value=openai_response(json.dumps(GROUNDED_QA_PAYLOAD)))
        )
    )
    adapter = OpenAITextAdapter(api_key="sk-test", model="allowlisted-chat", client=client)
    result = await adapter.generate_structured(sample_request())
    assert result.parsed["answer"].startswith("Clarify")
    assert result.usage.provider == "openai"
    client.responses.create.assert_awaited()


@pytest.mark.asyncio
async def test_gemini_text_parses_structured_json() -> None:
    generate = AsyncMock(return_value=gemini_response(json.dumps(GROUNDED_QA_PAYLOAD)))
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    adapter = GeminiTextAdapter(api_key="gem-test", model="allowlisted-chat", client=client)
    result = await adapter.generate_structured(sample_request())
    assert result.parsed["unsupported"] is False
    assert result.usage.provider == "gemini"


@pytest.mark.asyncio
async def test_deepseek_text_parses_structured_json() -> None:
    create = AsyncMock(
        return_value=chat_completion_response(json.dumps(GROUNDED_QA_PAYLOAD))
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    adapter = DeepSeekTextAdapter(api_key="ds-test", model="allowlisted-chat", client=client)
    result = await adapter.generate_structured(sample_request())
    assert result.parsed["confidence_label"] == "supported"
    assert result.usage.provider == "deepseek"
    # JSON mode requested
    kwargs = create.await_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_factory", "status", "exc_type"),
    [
        (
            lambda client: OpenAITextAdapter(api_key="x", model="m", client=client, max_retries=0),
            401,
            ProviderConfigurationError,
        ),
        (
            lambda client: OpenAITextAdapter(api_key="x", model="m", client=client, max_retries=0),
            429,
            ProviderTemporarilyUnavailable,
        ),
        (
            lambda client: DeepSeekTextAdapter(
                api_key="x", model="m", client=client, max_retries=0
            ),
            503,
            ProviderTemporarilyUnavailable,
        ),
    ],
)
async def test_text_adapters_map_http_errors(
    adapter_factory: Any,
    status: int,
    exc_type: type[Exception],
) -> None:
    failing = AsyncMock(side_effect=FakeHTTPStatusError(status))
    if status == 503:
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=failing))
        )
    else:
        client = SimpleNamespace(responses=SimpleNamespace(create=failing))
    adapter = adapter_factory(client)
    with pytest.raises(exc_type):
        await adapter.generate_structured(sample_request())


@pytest.mark.asyncio
async def test_openai_timeout_maps_to_temporarily_unavailable() -> None:
    class TimeoutErr(Exception):
        pass

    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=TimeoutErr("timeout waiting")))
    )
    adapter = OpenAITextAdapter(api_key="x", model="m", client=client, max_retries=0)
    with pytest.raises(ProviderTemporarilyUnavailable) as excinfo:
        await adapter.generate_structured(sample_request())
    assert excinfo.value.details["error_kind"] == "timeout"


@pytest.mark.asyncio
async def test_gemini_refusal_maps() -> None:
    class SafetyError(Exception):
        status_code = 400

        def __str__(self) -> str:
            return "blocked by safety filters"

    generate = AsyncMock(side_effect=SafetyError())
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    adapter = GeminiTextAdapter(api_key="x", model="m", client=client, max_retries=0)
    with pytest.raises(ProviderRefused):
        await adapter.generate_structured(sample_request())


@pytest.mark.asyncio
async def test_deepseek_blank_json_clarifies_once_then_fails() -> None:
    create = AsyncMock(
        side_effect=[
            chat_completion_response(""),
            chat_completion_response(""),
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    adapter = DeepSeekTextAdapter(api_key="x", model="m", client=client, max_retries=1)
    with pytest.raises(ProviderResponseInvalid):
        await adapter.generate_structured(sample_request())
    assert create.await_count == 2


@pytest.mark.asyncio
async def test_deepseek_malformed_then_valid_on_clarify() -> None:
    create = AsyncMock(
        side_effect=[
            chat_completion_response("not-json{{{"),
            chat_completion_response(json.dumps(GROUNDED_QA_PAYLOAD)),
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    adapter = DeepSeekTextAdapter(api_key="x", model="m", client=client, max_retries=1)
    result = await adapter.generate_structured(sample_request())
    assert result.parsed["unsupported"] is False
    assert create.await_count == 2


def test_missing_keys_fail_closed() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAITextAdapter(api_key="", model="m")
    with pytest.raises(ProviderConfigurationError):
        GeminiTextAdapter(api_key="", model="m")
    with pytest.raises(ProviderConfigurationError):
        DeepSeekTextAdapter(api_key="", model="m")
