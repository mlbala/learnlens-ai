#!/usr/bin/env bash
# Verify monorepo code layout without network calls.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

required=(
  apps/api/app/core/scaffold.py
  apps/api/app/main.py
  apps/api/app/api/v1/health.py
  apps/api/Dockerfile
  apps/web/package.json
  apps/web/app/page.tsx
  apps/web/Dockerfile
  packages/contracts/package.json
  infra/.gitkeep
  fixtures/.gitkeep
  Makefile
  compose.yaml
  .env.example
  .github/workflows/ci.yml
)

missing=0
for path in "${required[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "missing: $path"
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "layout check failed"
  exit 1
fi

echo "layout check ok"
