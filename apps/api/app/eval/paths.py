"""Resolve golden fixture paths relative to the monorepo root."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    # apps/api/app/eval/paths.py -> parents[4] = monorepo root
    return Path(__file__).resolve().parents[4]


def golden_root(override: Path | None = None) -> Path:
    if override is not None:
        return override.resolve()
    return repo_root() / "fixtures" / "golden"


def default_report_dir() -> Path:
    return repo_root() / "artifacts" / "eval"
