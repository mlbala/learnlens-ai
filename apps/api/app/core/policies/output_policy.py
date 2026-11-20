"""OutputPolicy — strip unsafe URLs, minimize PII in model-facing outputs."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.core.policies.privacy_policy import PrivacyPolicy

# Free-text URL-ish tokens (model may invent links; server citations are separate).
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_ALLOWED_HOSTS = frozenset(
    {
        "www.youtube.com",
        "youtube.com",
        "youtu.be",
        "www.youtu.be",
        "m.youtube.com",
    }
)
# Common secret / PII-ish fragments to scrub from assistant free text.
_PII_FRAGMENTS = re.compile(
    r"(?i)\b(ssn|social\s*security|credit\s*card|cvv|password\s*[:=])\b"
)


class OutputPolicy:
    """Post-validate model text for safe rendering and citation allowlists elsewhere."""

    @staticmethod
    def strip_disallowed_urls(text: str) -> str:
        """Remove or neutralize URLs that are not on the citation allowlist hosts."""

        def _replace(match: re.Match[str]) -> str:
            raw = match.group(0)
            try:
                parsed = urlparse(raw)
            except ValueError:
                return "[link removed]"
            host = (parsed.hostname or "").lower()
            if host in _ALLOWED_HOSTS and parsed.scheme in {"http", "https"}:
                return raw
            return "[link removed]"

        return _URL_RE.sub(_replace, text)

    @staticmethod
    def minimize_pii(text: str) -> str:
        cleaned = PrivacyPolicy.redact_text(text, redact_emails=True)
        cleaned = _PII_FRAGMENTS.sub("[redacted]", cleaned)
        return cleaned

    @staticmethod
    def sanitize_assistant_text(text: str) -> str:
        return OutputPolicy.minimize_pii(OutputPolicy.strip_disallowed_urls(text))

    # Free-text keys only — never rewrite opaque IDs (segment UUIDs, etc.).
    _TEXT_KEYS = frozenset({"answer", "text", "summary", "content", "snippet"})

    @staticmethod
    def sanitize_payload_strings(payload: dict[str, Any]) -> dict[str, Any]:
        """Sanitize free-text leaves; preserve citation/segment ID membership strings."""
        out: dict[str, Any] = {}
        for key, value in payload.items():
            key_l = str(key).lower()
            if key_l in OutputPolicy._TEXT_KEYS and isinstance(value, str):
                out[key] = OutputPolicy.sanitize_assistant_text(value)
            elif isinstance(value, dict):
                out[key] = OutputPolicy.sanitize_payload_strings(value)
            elif isinstance(value, list):
                out[key] = [
                    (
                        OutputPolicy.sanitize_payload_strings(item)
                        if isinstance(item, dict)
                        else item
                    )
                    for item in value
                ]
            else:
                out[key] = value
        return out
