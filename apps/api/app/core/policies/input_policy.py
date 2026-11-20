"""InputPolicy — size limits, upload filename rules, suspicious-content scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

_ALLOWED_EXTENSIONS = frozenset({".srt", ".vtt", ".txt"})
_TRAVERSAL = re.compile(r"(^|[\\/])\.\.([\\/]|$)")
_NULL_BYTE = re.compile(r"\x00")

# Heuristic signals only — never used alone to authorize or execute tools.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b"),
    re.compile(r"(?i)\bsystem\s*(update|override|prompt)\b"),
    re.compile(r"(?i)\byou\s+are\s+now\b"),
    re.compile(r"(?i)\b(exfiltrate|exfiltration)\b"),
    re.compile(r"(?i)\b(api[_-]?key|sk-[a-z0-9-]{8,})\b"),
    re.compile(r"(?i)https?://attacker\.|steal\?key="),
    re.compile(r"(?i)<\s*/?\s*system\s*>"),
    re.compile(r"(?i)\bdo\s+not\s+follow\s+(developer|system)\b"),
    re.compile(r"(?i)base64\s*[:=]"),
)


class InputPolicyViolation(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class SuspiciousScore:
    score: int
    matched: tuple[str, ...]


class InputPolicy:
    """Validate untrusted user/upload inputs. Fail closed on path / type abuse."""

    @staticmethod
    def sanitize_upload_filename(filename: str | None) -> str | None:
        """
        Return a basename-only filename with an allowlisted extension, or None.

        Rejects path traversal, null bytes, and non-transcript extensions.
        Storage keys are server-generated; this only gates content-type detection.
        """
        if filename is None:
            return None
        raw = filename.strip()
        if not raw or _NULL_BYTE.search(raw):
            raise InputPolicyViolation(
                "INVALID_FILENAME",
                "Upload filename is invalid.",
            )
        if _TRAVERSAL.search(raw) or raw.startswith(("/", "\\")):
            raise InputPolicyViolation(
                "INVALID_FILENAME",
                "Path traversal in upload filenames is not allowed.",
            )
        # Collapse Windows and POSIX path forms to the final component.
        base = PureWindowsPath(raw).name
        base = PurePosixPath(base).name
        if not base or base in {".", ".."} or _TRAVERSAL.search(base):
            raise InputPolicyViolation(
                "INVALID_FILENAME",
                "Path traversal in upload filenames is not allowed.",
            )
        lower = base.lower()
        if not any(lower.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
            raise InputPolicyViolation(
                "INVALID_TRANSCRIPT_TYPE",
                "Only .srt, .vtt, and .txt transcripts are supported.",
            )
        return base

    @staticmethod
    def enforce_text_size(
        text: str,
        *,
        max_characters: int,
        code: str = "PAYLOAD_TOO_LARGE",
    ) -> None:
        if len(text) > max_characters:
            raise InputPolicyViolation(
                code,
                f"Input exceeds the {max_characters} character limit.",
            )

    @staticmethod
    def score_suspicious_content(text: str) -> SuspiciousScore:
        matched: list[str] = []
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                matched.append(pattern.pattern)
        return SuspiciousScore(score=len(matched), matched=tuple(matched))

    @staticmethod
    def password_policy_error(
        password: str,
        *,
        min_length: int = 8,
        max_length: int = 128,
    ) -> str | None:
        if len(password) < min_length:
            return f"Password must be at least {min_length} characters."
        if len(password) > max_length:
            return f"Password must be at most {max_length} characters."
        if password.strip() != password or not password.strip():
            return "Password must not start or end with whitespace."
        has_letter = any(c.isalpha() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        if not has_letter:
            return "Password must include at least one letter."
        if not (has_digit or has_special):
            return "Password must include at least one digit or special character."
        return None
