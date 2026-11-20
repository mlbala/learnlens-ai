"""Smoke checks that the monorepo code layout exists."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "apps/api/app/core/scaffold.py",
    "apps/api/app/main.py",
    "apps/api/app/api/v1/health.py",
    "apps/api/app/api/v1/auth.py",
    "apps/api/app/api/v1/playlists.py",
    "apps/api/app/ai/factory.py",
    "apps/api/app/api/v1/settings_providers.py",
    "apps/api/app/domain/youtube_url.py",
    "apps/api/app/youtube/factory.py",
    "apps/api/app/db/models/identity.py",
    "apps/api/alembic/versions/20261118_0001_initial_schema.py",
    "apps/api/alembic/versions/20261119_0002_import_idempotency_result.py",
    "apps/api/alembic/versions/20261120_0003_summaries_provider_runs.py",
    "apps/api/app/domain/chunking.py",
    "apps/api/app/domain/chapter_boundaries.py",
    "apps/api/app/services/summarization.py",
    "apps/api/Dockerfile",
    "apps/api/scripts/docker-entrypoint.sh",
    "apps/web/package.json",
    "apps/web/app/page.tsx",
    "apps/web/Dockerfile",
    "packages/contracts/package.json",
    "infra/.gitkeep",
    "infra/deploy/DEPLOYMENT.md",
    "infra/deploy/BACKUP_RESTORE.md",
    "infra/deploy/INCIDENT_PLAYBOOK.md",
    "infra/deploy/PRIVACY_AND_COMPLIANCE.md",
    "infra/licenses/DEPENDENCY_LICENSES.md",
    "infra/licenses/dependency-licenses.json",
    "scripts/check_layout.sh",
    "scripts/license_inventory.py",
    "fixtures/youtube/videos.json",
    "fixtures/youtube/playlist_pages.json",
    "fixtures/transcripts/sample.srt",
    "fixtures/transcripts/malicious_prompt.vtt",
    "apps/api/app/domain/transcript_parse.py",
    "apps/api/app/workers/tasks.py",
    "apps/api/app/storage/local.py",
    "apps/api/app/api/v1/jobs.py",
    "apps/api/tests/test_e2e_smoke.py",
    "Makefile",
    "compose.yaml",
    "compose.prod.yaml",
    ".env.example",
    ".github/workflows/ci.yml",
)


def test_required_scaffold_paths_exist() -> None:
    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).exists()]
    assert missing == [], f"missing scaffold paths: {missing}"
