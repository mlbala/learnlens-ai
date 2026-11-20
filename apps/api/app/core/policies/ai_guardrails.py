"""Central AI guardrails — applied to every text-model call across the app.

Layers (docs/06_SECURITY_GUARDRAILS.md):
- Input: size caps + suspicious scoring (never authorize tools from text)
- Evidence: treat packet as untrusted quoted data; no secrets in evidence
- Output: strip unsafe URLs / minimize PII before schema/citation gates
- No shell/browser/secret-read capabilities are exposed to models
"""

from __future__ import annotations

import logging
from typing import Any

from app.ai.contracts import ModelRequest, ModelResult, TextModel
from app.core.policies.input_policy import InputPolicy, InputPolicyViolation
from app.core.policies.output_policy import OutputPolicy
from app.core.policies.privacy_policy import PrivacyPolicy

logger = logging.getLogger(__name__)

# Keys that must never appear in evidence packets sent to providers.
_FORBIDDEN_EVIDENCE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
        "refresh_token",
        "session_secret",
        "database_url",
        "openai_api_key",
        "gemini_api_key",
        "deepseek_api_key",
    }
)


class AiGuardrailError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AiGuardrails:
    """Deterministic pre/post gates around provider-neutral TextModel calls."""

    @staticmethod
    def enforce_user_text(
        text: str,
        *,
        max_characters: int,
        code: str = "INPUT_TOO_LARGE",
        allow_empty: bool = False,
    ) -> str:
        cleaned = text.strip()
        if not cleaned and not allow_empty:
            raise AiGuardrailError("EMPTY_INPUT", "Input must not be empty.")
        try:
            InputPolicy.enforce_text_size(cleaned, max_characters=max_characters, code=code)
        except InputPolicyViolation as exc:
            raise AiGuardrailError(exc.code, exc.message) from exc
        suspicion = InputPolicy.score_suspicious_content(cleaned)
        if suspicion.score > 0:
            # Do not block user questions that quote malicious text — log only.
            logger.info(
                "ai_input_suspicion",
                extra={
                    "suspicion_score": suspicion.score,
                    "matched_count": len(suspicion.matched),
                },
            )
        return cleaned

    @staticmethod
    def sanitize_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop secret-like keys and redact emails from evidence text leaves."""
        cleaned: list[dict[str, Any]] = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            row: dict[str, Any] = {}
            for key, value in item.items():
                key_l = str(key).lower()
                if key_l in _FORBIDDEN_EVIDENCE_KEYS:
                    continue
                if key_l in {"text", "content", "snippet", "title"} and isinstance(value, str):
                    row[key] = PrivacyPolicy.redact_text(value, redact_emails=True)
                else:
                    row[key] = value
            # Opaque provenance marker for adapters / prompts.
            row.setdefault("untrusted", True)
            cleaned.append(row)
        return cleaned

    @staticmethod
    def prepare_request(
        request: ModelRequest,
        *,
        max_input_characters: int,
    ) -> ModelRequest:
        """Cap input size and sanitize evidence before any provider call."""
        evidence = AiGuardrails.sanitize_evidence(list(request.evidence or []))
        user_input = request.user_input or ""
        if len(user_input) > max_input_characters:
            raise AiGuardrailError(
                "AI_INPUT_TOO_LARGE",
                f"Model input exceeds the {max_input_characters} character limit.",
            )
        # Instructions stay server-authored; never merge raw user text into them.
        return ModelRequest(
            purpose=request.purpose,
            instructions=request.instructions,
            user_input=user_input,
            evidence=evidence,
            response_schema=request.response_schema,
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
            timeout_seconds=request.timeout_seconds,
            prompt_version=request.prompt_version,
        )

    @staticmethod
    def sanitize_result(result: ModelResult) -> ModelResult:
        parsed = result.parsed if isinstance(result.parsed, dict) else {}
        safe = OutputPolicy.sanitize_payload_strings(parsed)
        return ModelResult(
            parsed=safe,
            usage=result.usage,
            raw_text=(
                OutputPolicy.sanitize_assistant_text(result.raw_text)
                if isinstance(result.raw_text, str)
                else result.raw_text
            ),
        )


class GuardedTextModel:
    """Decorator TextModel — every generate_structured goes through AiGuardrails."""

    def __init__(
        self,
        inner: TextModel,
        *,
        max_input_characters: int,
    ) -> None:
        self._inner = inner
        self._max_input_characters = max_input_characters

    @property
    def provider(self) -> str:
        return self._inner.provider

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def capabilities(self):  # type: ignore[no-untyped-def]
        return self._inner.capabilities

    async def generate_structured(self, request: ModelRequest) -> ModelResult:
        prepared = AiGuardrails.prepare_request(
            request,
            max_input_characters=self._max_input_characters,
        )
        result = await self._inner.generate_structured(prepared)
        return AiGuardrails.sanitize_result(result)

    async def health(self) -> dict[str, str]:
        return await self._inner.health()
