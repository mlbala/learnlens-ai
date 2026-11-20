"""Pluggable prompt-injection / content scanners for AI guardrails.

Preferred production backend: NVIDIA NeMo Guardrails (actively maintained).
Protect AI LLM Guard was archived July 2026 — do not adopt for new work.

Deterministic app gates (auth, citations, schema, size) remain the fail-closed
floor; scanners only *augment* them (docs/06_SECURITY_GUARDRAILS.md).
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class ScanChannel(StrEnum):
    """Where the text came from — changes block vs quarantine policy."""

    USER_DIRECT = "user_direct"  # chat question / user-authored prompt
    EVIDENCE_INDIRECT = "evidence_indirect"  # transcript / RAG packet
    MODEL_OUTPUT = "model_output"


class ScanVerdict(StrEnum):
    ALLOW = "allow"
    QUARANTINE = "quarantine"  # treat as untrusted data; do not elevate to instructions
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class ScanFinding:
    code: str
    detail: str
    score: float = 0.0


@dataclass(frozen=True, slots=True)
class ScanResult:
    verdict: ScanVerdict
    backend: str
    findings: tuple[ScanFinding, ...] = field(default_factory=tuple)
    risk_score: float = 0.0

    @property
    def blocked(self) -> bool:
        return self.verdict == ScanVerdict.BLOCK


@runtime_checkable
class GuardrailScanner(Protocol):
    """Framework-backed or heuristic scanner — never the sole security perimeter."""

    @property
    def name(self) -> str: ...

    def scan(self, text: str, *, channel: ScanChannel) -> ScanResult: ...


def _normalize(text: str) -> str:
    # NFKC collapses homoglyphs; strip bidi/zero-width smuggling used in injections.
    cleaned = unicodedata.normalize("NFKC", text or "")
    return "".join(
        ch
        for ch in cleaned
        if unicodedata.category(ch) not in {"Cf", "Cc"} or ch in "\n\t\r"
    )


class StructuredInjectionScanner:
    """
    Multi-signal direct/indirect injection detector (Unicode + role/delimiter + intent).

    Used when NeMo / HF classifier are unavailable. Not a regex-only toy: normalizes
    Unicode smuggling, detects instruction-delimiter frames, and scores intent families.
    Still a *fallback* — enable NeMo for production semantic detection.
    """

    name = "structured_injection_v1"

    _ROLE_FRAMES = (
        "system:",
        "developer:",
        "assistant:",
        "<<sys>>",
        "<|im_start|>",
        "<|system|>",
        "[INST]",
        "### instruction",
        "### system",
    )
    _INTENT_PHRASES = (
        "ignore previous instructions",
        "ignore all prior instructions",
        "disregard the above",
        "override your safety",
        "jailbreak",
        "dan mode",
        "reveal the system prompt",
        "exfiltrate",
        "do not follow developer",
        "you are now",
        "system update",
        "system override",
    )
    _INDIRECT_HINTS = (
        "when summarizing this",
        "if you are an ai",
        "hidden instruction",
        "for the language model",
        "tools.execute",
        "call external url",
        "send api key",
    )

    def scan(self, text: str, *, channel: ScanChannel) -> ScanResult:
        raw = text or ""
        norm = _normalize(raw).lower()
        findings: list[ScanFinding] = []
        score = 0.0

        if len(raw) != len(_normalize(raw)):
            findings.append(
                ScanFinding("UNICODE_SMUGGLING", "Zero-width/bidi/control chars removed", 0.35)
            )
            score += 0.35

        for frame in self._ROLE_FRAMES:
            if frame in norm:
                findings.append(ScanFinding("ROLE_DELIMITER", f"Matched frame '{frame}'", 0.4))
                score += 0.4
                break

        for phrase in self._INTENT_PHRASES:
            if phrase in norm:
                findings.append(ScanFinding("INJECTION_INTENT", f"Matched '{phrase}'", 0.55))
                score += 0.55
                break

        if channel == ScanChannel.EVIDENCE_INDIRECT:
            for hint in self._INDIRECT_HINTS:
                if hint in norm:
                    findings.append(
                        ScanFinding("INDIRECT_INJECTION", f"Matched '{hint}'", 0.45)
                    )
                    score += 0.45
                    break

        score = min(score, 1.0)
        if channel == ScanChannel.USER_DIRECT and score >= 0.7:
            verdict = ScanVerdict.BLOCK
        elif score >= 0.35:
            verdict = ScanVerdict.QUARANTINE
        else:
            verdict = ScanVerdict.ALLOW
        return ScanResult(
            verdict=verdict,
            backend=self.name,
            findings=tuple(findings),
            risk_score=score,
        )


class HuggingFaceInjectionScanner:
    """
    Local text-classification scanner (ProtectAI DeBERTa prompt-injection family).

    Requires optional extras: transformers + torch. Same model family NeMo HF rails use.
    """

    name = "hf_prompt_injection"

    def __init__(
        self,
        *,
        model_id: str = "ProtectAI/deberta-v3-base-prompt-injection-v2",
        threshold: float = 0.5,
    ) -> None:
        self._model_id = model_id
        self._threshold = threshold
        self._pipe: Any | None = None

    def _ensure_pipeline(self) -> Any:
        if self._pipe is not None:
            return self._pipe
        try:
            from transformers import pipeline  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "transformers is not installed; pip install with guardrails-ml extra"
            ) from exc
        self._pipe = pipeline(
            "text-classification",
            model=self._model_id,
            truncation=True,
            max_length=512,
        )
        return self._pipe

    def scan(self, text: str, *, channel: ScanChannel) -> ScanResult:
        pipe = self._ensure_pipeline()
        sample = _normalize(text)[:4_000] or " "
        raw = pipe(sample)[0]
        label = str(raw.get("label") or "").upper()
        conf = float(raw.get("score") or 0.0)
        is_injection = label in {"INJECTION", "LABEL_1", "1"} and conf >= self._threshold
        findings = (
            (
                ScanFinding(
                    "HF_PROMPT_INJECTION",
                    f"label={label} confidence={conf:.3f}",
                    conf,
                ),
            )
            if is_injection
            else ()
        )
        if not is_injection:
            return ScanResult(
                verdict=ScanVerdict.ALLOW,
                backend=self.name,
                findings=(),
                risk_score=conf if label in {"INJECTION", "LABEL_1", "1"} else 0.0,
            )
        if channel == ScanChannel.USER_DIRECT:
            verdict = ScanVerdict.BLOCK
        else:
            # Indirect (evidence): quarantine — still usable as quoted source text.
            verdict = ScanVerdict.QUARANTINE
        return ScanResult(
            verdict=verdict,
            backend=self.name,
            findings=findings,
            risk_score=conf,
        )


class NemoGuardrailsScanner:
    """
    NVIDIA NeMo Guardrails adapter (check-only; no generative self-check by default).

    Loads Colang/YAML from apps/api/guardrails/nemo. Prefer HF classifier rails so
    checks do not require a paid chat LLM. Falls back to StructuredInjectionScanner
    actions registered in config when models are unavailable.
    """

    name = "nemo_guardrails"

    def __init__(self, *, config_path: str, threshold: float = 0.5) -> None:
        self._config_path = config_path
        self._threshold = threshold
        self._rails: Any | None = None
        self._fallback = StructuredInjectionScanner()

    def _ensure_rails(self) -> Any | None:
        if self._rails is not None:
            return self._rails
        try:
            from nemoguardrails import LLMRails, RailsConfig  # type: ignore[import-not-found]
        except ImportError:
            logger.warning(
                "nemoguardrails_not_installed",
                extra={"hint": "uv sync --extra guardrails"},
            )
            return None
        try:
            config = RailsConfig.from_path(self._config_path)
            self._rails = LLMRails(config)
        except Exception as exc:  # noqa: BLE001 — degrade to structured scanner
            logger.warning(
                "nemo_config_load_failed",
                extra={"error_type": type(exc).__name__, "path": self._config_path},
            )
            return None
        return self._rails

    def scan(self, text: str, *, channel: ScanChannel) -> ScanResult:
        rails = self._ensure_rails()
        if rails is None:
            return self._fallback.scan(text, channel=channel)

        role = "user" if channel != ScanChannel.MODEL_OUTPUT else "assistant"
        messages = [{"role": role, "content": _normalize(text)[:8_000]}]
        try:
            # Prefer async API when available; sync check is fine in worker threads.
            result = rails.check(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "nemo_check_failed",
                extra={"error_type": type(exc).__name__, "channel": channel.value},
            )
            return self._fallback.scan(text, channel=channel)

        status = str(getattr(result, "status", "") or "").lower()
        blocked = "block" in status or "rail" in status and "pass" not in status
        # Some versions expose .blocked / .ok
        if hasattr(result, "blocked"):
            blocked = bool(result.blocked)
        elif hasattr(result, "ok"):
            blocked = not bool(result.ok)

        if not blocked:
            # Still run structured pass for Unicode smuggling NeMo may miss.
            secondary = self._fallback.scan(text, channel=channel)
            if secondary.verdict == ScanVerdict.ALLOW:
                return ScanResult(
                    verdict=ScanVerdict.ALLOW,
                    backend=self.name,
                    findings=(),
                    risk_score=0.0,
                )
            return ScanResult(
                verdict=secondary.verdict,
                backend=f"{self.name}+{secondary.backend}",
                findings=secondary.findings,
                risk_score=secondary.risk_score,
            )

        finding = ScanFinding("NEMO_RAIL_BLOCK", f"NeMo status={status}", 1.0)
        if channel == ScanChannel.USER_DIRECT:
            verdict = ScanVerdict.BLOCK
        elif channel == ScanChannel.MODEL_OUTPUT:
            verdict = ScanVerdict.BLOCK
        else:
            verdict = ScanVerdict.QUARANTINE
        return ScanResult(
            verdict=verdict,
            backend=self.name,
            findings=(finding,),
            risk_score=1.0,
        )


class CompositeGuardrailScanner:
    """Run primary framework scanner; always keep structured secondary signals."""

    def __init__(self, primary: GuardrailScanner, secondary: GuardrailScanner) -> None:
        self._primary = primary
        self._secondary = secondary

    @property
    def name(self) -> str:
        return f"composite:{self._primary.name}+{self._secondary.name}"

    def scan(self, text: str, *, channel: ScanChannel) -> ScanResult:
        primary = self._primary.scan(text, channel=channel)
        secondary = self._secondary.scan(text, channel=channel)
        # Most severe verdict wins.
        order = {ScanVerdict.ALLOW: 0, ScanVerdict.QUARANTINE: 1, ScanVerdict.BLOCK: 2}
        verdict = (
            primary.verdict
            if order[primary.verdict] >= order[secondary.verdict]
            else secondary.verdict
        )
        findings = tuple(list(primary.findings) + list(secondary.findings))
        return ScanResult(
            verdict=verdict,
            backend=self.name,
            findings=findings,
            risk_score=max(primary.risk_score, secondary.risk_score),
        )


_scanner_singleton: GuardrailScanner | None = None


def reset_guardrail_scanner() -> None:
    global _scanner_singleton
    _scanner_singleton = None


def build_guardrail_scanner(
    *,
    backend: str,
    nemo_config_path: str,
    hf_model_id: str,
    hf_threshold: float,
) -> GuardrailScanner:
    """
    backend:
      - deterministic | structured: multi-signal structured scanner only
      - hf | classifier: HuggingFace DeBERTa prompt-injection (+ structured)
      - nemo: NeMo Guardrails (+ structured)
      - auto: nemo if installed, else hf if installed, else structured
    """
    name = (backend or "auto").strip().lower()
    structured = StructuredInjectionScanner()

    def _try_hf() -> GuardrailScanner | None:
        try:
            import transformers  # noqa: F401 # type: ignore[import-not-found]

            return CompositeGuardrailScanner(
                HuggingFaceInjectionScanner(model_id=hf_model_id, threshold=hf_threshold),
                structured,
            )
        except Exception:
            return None

    def _try_nemo() -> GuardrailScanner | None:
        try:
            import nemoguardrails  # noqa: F401 # type: ignore[import-not-found]

            return CompositeGuardrailScanner(
                NemoGuardrailsScanner(config_path=nemo_config_path, threshold=hf_threshold),
                structured,
            )
        except Exception:
            return None

    if name in {"deterministic", "structured", "builtin"}:
        return structured
    if name in {"hf", "classifier", "huggingface"}:
        return _try_hf() or structured
    if name == "nemo":
        # NeMo package first; same HF classifier NeMo docs recommend as fallback.
        return _try_nemo() or _try_hf() or structured
    # auto
    return _try_nemo() or _try_hf() or structured


def get_guardrail_scanner(
    *,
    backend: str = "auto",
    nemo_config_path: str = "",
    hf_model_id: str = "ProtectAI/deberta-v3-base-prompt-injection-v2",
    hf_threshold: float = 0.5,
) -> GuardrailScanner:
    global _scanner_singleton
    if _scanner_singleton is None:
        _scanner_singleton = build_guardrail_scanner(
            backend=backend,
            nemo_config_path=nemo_config_path,
            hf_model_id=hf_model_id,
            hf_threshold=hf_threshold,
        )
    return _scanner_singleton
