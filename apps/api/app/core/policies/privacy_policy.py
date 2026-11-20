"""PrivacyPolicy — secret / transcript redaction for logs and public errors."""

from __future__ import annotations

import re
from typing import Any

from app.ai.schema_parse import redact_secrets

# Long opaque tokens (API keys). Exclude UUID shape (8-4-4-4-12) used as segment IDs.
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_LONG_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


class PrivacyPolicy:
    """Redact secrets and avoid logging raw transcript text."""

    @staticmethod
    def redact_text(text: str, *, redact_emails: bool = False) -> str:
        if _UUID.match(text.strip()):
            return text
        cleaned = redact_secrets(text)
        cleaned = _BEARER.sub(r"\1[REDACTED]", cleaned)

        def _token(match: re.Match[str]) -> str:
            raw = match.group(0)
            return raw if _UUID.match(raw) else "[REDACTED]"

        cleaned = _LONG_TOKEN.sub(_token, cleaned)
        if redact_emails:
            cleaned = _EMAIL.sub("[REDACTED_EMAIL]", cleaned)
        return cleaned

    @staticmethod
    def redact_mapping(data: dict[str, Any] | None) -> dict[str, Any]:
        if not data:
            return {}
        out: dict[str, Any] = {}
        for key, value in data.items():
            key_l = str(key).lower()
            if any(
                s in key_l
                for s in ("password", "secret", "api_key", "token", "authorization", "cookie")
            ):
                out[key] = "[REDACTED]"
                continue
            if isinstance(value, str):
                out[key] = PrivacyPolicy.redact_text(value)
            elif isinstance(value, dict):
                out[key] = PrivacyPolicy.redact_mapping(value)
            else:
                out[key] = value
        return out

    @staticmethod
    def safe_error_message(message: str) -> str:
        return PrivacyPolicy.redact_text(message)

    @staticmethod
    def transcript_log_safe(
        *,
        character_count: int,
        cue_count: int | None = None,
    ) -> dict[str, Any]:
        """Metadata-only summary for operational logs (never cue text)."""
        payload: dict[str, Any] = {"character_count": character_count}
        if cue_count is not None:
            payload["cue_count"] = cue_count
        return payload
