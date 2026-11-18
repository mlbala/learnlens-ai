"""JSON structured-output parsing with lightweight JSON-Schema checks (Pydantic-friendly)."""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai.errors import ProviderResponseInvalid

_SECRETISH = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer\s+[a-z0-9\-._~+/]+=*|sk-[a-z0-9]+)"
)


def redact_secrets(text: str) -> str:
    return _SECRETISH.sub("[REDACTED]", text)


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model text; tolerate fenced markdown."""
    cleaned = text.strip()
    if not cleaned:
        raise ProviderResponseInvalid(
            "Provider returned blank structured output.",
            details={"error_kind": "blank_json"},
        )
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderResponseInvalid(
            "Provider returned malformed JSON.",
            details={"error_kind": "malformed_json"},
        ) from exc
    if not isinstance(data, dict):
        raise ProviderResponseInvalid(
            "Structured output must be a JSON object.",
            details={"error_kind": "not_object"},
        )
    return data


def _type_ok(value: Any, expected: str) -> bool:
    mapping: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
        "null": type(None),
    }
    py = mapping.get(expected)
    if py is None:
        return True
    if expected == "number" and isinstance(value, bool):
        return False
    if expected == "integer" and isinstance(value, bool):
        return False
    return isinstance(value, py)


def validate_against_schema(
    data: dict[str, Any],
    response_schema: dict[str, Any],
    *,
    provider: str | None = None,
) -> dict[str, Any]:
    """
    Validate parsed JSON against a subset of JSON Schema (type/required/properties).

    Full Draft validators are deferred; adapters still fail closed on mismatch.
    """
    try:
        _validate_node(data, response_schema)
    except ValueError as exc:
        raise ProviderResponseInvalid(
            "Structured output failed schema validation.",
            provider=provider,
            details={"error_kind": "schema_validation"},
        ) from exc
    return data


def _validate_node(value: Any, schema: dict[str, Any]) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _type_ok(value, expected_type):
        raise ValueError(f"expected type {expected_type}")
    if isinstance(expected_type, list) and not any(
        _type_ok(value, t) for t in expected_type if isinstance(t, str)
    ):
        raise ValueError("expected one of union types")

    if schema.get("type") == "object" or "properties" in schema or "required" in schema:
        if not isinstance(value, dict):
            raise ValueError("expected object")
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                raise ValueError(f"missing required property {key}")
        properties = schema.get("properties") or {}
        for key, subschema in properties.items():
            if key in value and isinstance(subschema, dict):
                _validate_node(value[key], subschema)

    if schema.get("type") == "array" or "items" in schema:
        if not isinstance(value, list):
            raise ValueError("expected array")
        items = schema.get("items")
        if isinstance(items, dict):
            for item in value:
                _validate_node(item, items)
