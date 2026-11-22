"""Resolve golden fixture paths relative to the monorepo root."""

from __future__ import annotations

from pathlib import Path

from app.core.paths import repo_root as monorepo_root


def repo_root() -> Path:
    return monorepo_root()


def golden_root(override: Path | None = None) -> Path:
    if override is not None:
        return override.resolve()
    return repo_root() / "fixtures" / "golden"


def default_report_dir() -> Path:
    return repo_root() / "artifacts" / "eval"
