"""Shared schemas and mock helpers for AI adapter tests (fixture data only)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.ai.contracts import ModelRequest

GROUNDED_QA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["answer", "claims", "unsupported", "confidence_label"],
    "properties": {
        "answer": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "citation_segment_ids"],
                "properties": {
                    "text": {"type": "string"},
                    "citation_segment_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "unsupported": {"type": "boolean"},
        "confidence_label": {"type": "string"},
    },
}

GROUNDED_QA_PAYLOAD: dict[str, Any] = {
    "answer": "Clarify requirements before coding [1].",
    "claims": [
        {
            "text": "Clarify requirements before coding.",
            "citation_segment_ids": ["seg_fixture_01"],
        }
    ],
    "unsupported": False,
    "confidence_label": "supported",
}


def sample_request(**overrides: Any) -> ModelRequest:
    base = ModelRequest(
        purpose="grounded_qa",
        instructions="Answer using only evidence.",
        user_input="What should I do first?",
        evidence=[{"id": "seg_fixture_01", "text": "Fixture: clarify requirements."}],
        response_schema=GROUNDED_QA_SCHEMA,
        max_output_tokens=400,
        temperature=0.0,
        timeout_seconds=5,
        prompt_version="test-v1",
    )
    if not overrides:
        return base
    data = base.__dict__.copy()
    data.update(overrides)
    return ModelRequest(**data)


class FakeHTTPStatusError(Exception):
    def __init__(self, status_code: int, message: str = "upstream") -> None:
        super().__init__(message)
        self.status_code = status_code


def openai_response(text: str, *, response_id: str = "resp_test") -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        output_text=text,
        output=[],
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )


def chat_completion_response(text: str, *, response_id: str = "chat_test") -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=22),
    )


def gemini_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        candidates=[],
        usage_metadata=SimpleNamespace(prompt_token_count=9, candidates_token_count=18),
        response_id="gem_test",
    )
