"""Pure scaffolding helpers — no network, no DB, no providers."""

from __future__ import annotations


def project_slug(name: str) -> str:
    """Normalize a display name into a lowercase hyphenated slug."""
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    parts = [p for p in cleaned.split("-") if p]
    if not parts:
        raise ValueError("name must contain at least one alphanumeric character")
    return "-".join(parts)
