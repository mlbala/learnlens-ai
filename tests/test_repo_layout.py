"""Smoke checks that the monorepo code layout exists."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "apps/api/app/core/scaffold.py",
    "apps/api/app/main.py",
    "apps/api/app/api/v1/health.py",
    "apps/api/Dockerfile",
    "apps/web/package.json",
    "apps/web/app/page.tsx",
    "apps/web/Dockerfile",
    "packages/contracts/package.json",
    "infra/.gitkeep",
    "scripts/check_layout.sh",
    "fixtures/.gitkeep",
    "Makefile",
    "compose.yaml",
    ".env.example",
)


def test_required_scaffold_paths_exist() -> None:
    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).exists()]
    assert missing == [], f"missing scaffold paths: {missing}"
