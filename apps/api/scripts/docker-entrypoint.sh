#!/bin/sh
# API/worker container entrypoint.
# When RUN_MIGRATIONS=1, apply Alembic upgrades before the main process.
# Secrets must come from the environment — never bake credentials into the image.
set -eu

if [ "${RUN_MIGRATIONS:-0}" = "1" ] || [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "entrypoint: applying alembic migrations (upgrade head)"
  alembic upgrade head
fi

exec "$@"
