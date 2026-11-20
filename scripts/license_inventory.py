#!/usr/bin/env python3
"""Write infra/licenses/dependency-licenses.json from installed package metadata.

Offline only — no network. Run from repo root after `uv sync --project apps/api`.
"""

from __future__ import annotations

import importlib.metadata as md
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "infra" / "licenses" / "dependency-licenses.json"

API_PKGS = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pydantic-settings",
    "sqlalchemy",
    "alembic",
    "asyncpg",
    "argon2-cffi",
    "itsdangerous",
    "qdrant-client",
    "openai",
    "google-genai",
    "celery",
    "redis",
    "python-multipart",
]

WEB_HIGHLIGHTS = [
    ("next", "MIT", "apps/web"),
    ("react", "MIT", "apps/web"),
    ("react-dom", "MIT", "apps/web"),
    ("typescript", "Apache-2.0", "apps/web"),
    ("vitest", "MIT", "apps/web (dev)"),
    ("tailwindcss", "MIT", "apps/web"),
]


def _license_for(dist: md.Distribution) -> str:
    meta = dist.metadata
    lic = meta.get("License") or meta.get("License-Expression")
    if lic:
        return lic.replace("\n", " ").strip()
    classifiers = meta.get_all("Classifier") or []
    lic_class = [c.split("::")[-1].strip() for c in classifiers if c.startswith("License ::")]
    return "; ".join(lic_class) if lic_class else "UNKNOWN"


def main() -> int:
    rows: list[dict[str, str]] = []
    for name in API_PKGS:
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            rows.append(
                {
                    "name": name,
                    "version": "?",
                    "license": "see package metadata",
                    "ecosystem": "python",
                }
            )
            continue
        rows.append(
            {
                "name": dist.metadata["Name"],
                "version": dist.version,
                "license": _license_for(dist),
                "ecosystem": "python",
            }
        )

    payload = {
        "_comment": (
            "Inventory of primary LearnLens dependencies for operator review. "
            "Not legal advice. Regenerate with scripts/license_inventory.py when deps change."
        ),
        "generated_offline": True,
        "python_direct": rows,
        "javascript_highlights": [
            {"name": n, "license": lic, "scope": scope} for n, lic, scope in WEB_HIGHLIGHTS
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} python entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
