"""Attribute sanitization for traces/logs — never emit raw transcripts or secrets."""

from __future__ import annotations

import re
from typing import Any

# Keys that must never appear as span attributes (case-insensitive substring match).
_FORBIDDEN_KEY_FRAGMENTS = (
    "transcript",
    "cue_text",
    "raw_text",
    "content_text",
    "password",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "token",
    "prompt",
    "evidence_text",
    "message_content",
)

_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_LONG_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*")


def _redact_text(text: str) -> str:
    """Local redaction — avoids importing PrivacyPolicy (circular with ai package)."""
    if _UUID.match(text.strip()):
        return text
    cleaned = _BEARER.sub(r"\1[REDACTED]", text)

    def _token(match: re.Match[str]) -> str:
        raw = match.group(0)
        return raw if _UUID.match(raw) else "[REDACTED]"

    return _LONG_TOKEN.sub(_token, cleaned)


def sanitize_span_attributes(attrs: dict[str, Any] | None) -> dict[str, Any]:
    """
    Return a safe attribute map for OpenTelemetry-compatible spans / structured logs.

    Drops forbidden keys and redacts secret-shaped values. Never stores cue/transcript body.
    """
    if not attrs:
        return {}
    out: dict[str, Any] = {}
    for key, value in attrs.items():
        key_l = str(key).lower()
        if any(frag in key_l for frag in _FORBIDDEN_KEY_FRAGMENTS):
            continue
        if isinstance(value, str):
            cleaned = _redact_text(value)
            out[key] = cleaned[:512] if len(cleaned) > 512 else cleaned
        elif isinstance(value, (int, float, bool)) or value is None:
            out[key] = value
        elif isinstance(value, dict):
            out[key] = sanitize_span_attributes(value)
        elif isinstance(value, (list, tuple)):
            safe_list: list[Any] = []
            for item in value[:32]:
                if isinstance(item, str):
                    safe_list.append(_redact_text(item)[:128])
                elif isinstance(item, (int, float, bool)) or item is None:
                    safe_list.append(item)
            out[key] = safe_list
        else:
            out[key] = type(value).__name__
    return out
