"""Filesystem roots that work in monorepo checkout and Docker (/app) layouts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def api_package_root() -> Path:
    """Directory that contains the `app` package (…/apps/api or /app)."""
    # paths.py → core → app → <api root>
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """
    Monorepo root when present (compose.yaml / .git / fixtures).

    Inside the API container the layout is `/app/app/...` with optional
    `/app/fixtures/...`, so this returns `/app` there.
    """
    start = Path(__file__).resolve().parent
    for candidate in (start, *start.parents):
        if (candidate / "compose.yaml").is_file():
            return candidate
        if (candidate / ".git").exists():
            return candidate
        if (candidate / "fixtures" / "youtube").is_dir():
            return candidate
        if (candidate / "fixtures" / "golden").is_dir():
            return candidate
        if candidate.parent == candidate:
            break
    return api_package_root()
