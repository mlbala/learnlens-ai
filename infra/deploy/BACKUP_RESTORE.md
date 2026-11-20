# Backup and restore (Neon + Qdrant Cloud)

LearnLens does not ship local Postgres/Qdrant volumes. Backups are cloud-native.

## Neon (Postgres)

### Backup

1. Neon continuous PITR / branches — use the Neon console for the project.
2. Optional logical dump (operator machine; never commit dump files):

```bash
# Requires DATABASE_URL_UNPOOLED and neon/psql tooling on the operator host.
pg_dump "$DATABASE_URL_UNPOOLED" --format=custom --file="learnlens-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

3. Store dumps encrypted at rest; redact connection strings from shell history where possible.

### Restore

1. Prefer Neon branch restore / PITR when available.
2. Logical restore into a **new** database/branch first; validate with `make migrate` (should be no-op at head) and `/health/ready`.
3. Point `DATABASE_URL` / `DATABASE_URL_UNPOOLED` at the restored endpoint only after smoke checks.

```bash
# Example restore into an empty DB (destructive — confirm target first)
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL_UNPOOLED" learnlens-YYYYMMDD.dump
```

## Qdrant Cloud

1. Use Qdrant Cloud snapshots / cluster backup features for the collection used by LearnLens.
2. After restore, confirm collection dimension matches `AI_EMBED_DIMENSIONS` / embedding profile — incompatible dimensions must not append (fail closed).
3. Re-index from Neon source assets if vectors are missing; jobs are idempotent by content hash.

## Redis

Broker state is ephemeral in the Compose sample. Losing Redis may require re-queueing failed jobs; durable job rows live in Neon. Prefer `recover_expired_leases` (see observability runbook) over blind replays.

## Demo verification (no production data)

Offline CI does **not** perform live backup/restore. Operators should document the last successful Neon restore drill in their own ops notes.
