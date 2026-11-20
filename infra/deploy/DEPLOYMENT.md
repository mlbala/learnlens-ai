# LearnLens deployment guide

**Do not deploy without operator permission and real credentials.** This document is the production-like checklist for phase 16.

## Topology

| Component | Runtime | Notes |
| --- | --- | --- |
| `web` | Next.js container (or optional Vercel) | Talks to API via `API_INTERNAL_URL` |
| `api` | FastAPI / uvicorn container | Stateless; secrets from env |
| `worker` | Same API image, Celery CMD | Requires Redis; `CELERY_TASK_ALWAYS_EAGER=false` |
| Postgres | **Neon** (cloud) | No local DB volume |
| Vectors | **Qdrant Cloud** | No local Qdrant volume |
| Redis | Compose service or managed | Broker only in sample |

Fake AI providers remain the default (`AI_CHAT_PROVIDER=fake`, `AI_EMBED_PROVIDER=fake`, `YOUTUBE_METADATA_PROVIDER=fake`). Switch live providers only after quotas and keys are intentional.

## Configuration

1. Copy `.env.example` → a secrets store / host env (never commit `.env`).
2. Required for readiness: `DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `SESSION_SECRET`.
3. Migrations prefer `DATABASE_URL_UNPOOLED` (Neon direct).
4. Set `COOKIE_SECURE=true` and exact `CORS_ORIGINS` behind HTTPS.
5. Keep `ALLOW_TEST_SEED=false` in every shared/production environment.

See also: `docs/08_DEVOPS_OBSERVABILITY_COST.md`, `infra/observability/RUNBOOK.md`.

## Production-like Compose sample

```bash
# Export secrets in the shell or a secrets manager — not in git.
export DATABASE_URL=... DATABASE_URL_UNPOOLED=...
export QDRANT_URL=... QDRANT_API_KEY=...
export SESSION_SECRET=...   # long random value
export CORS_ORIGINS=https://app.example.com

docker compose -f compose.prod.yaml up --build
```

`compose.prod.yaml` runs a one-shot `migrate` service (`alembic upgrade head`) before API/worker. Images: `learnlens-api` (API + worker) and `learnlens-web`.

Local profile shortcuts:

```bash
make docker-build
docker compose --profile redis up -d
docker compose --profile app up --build
# Optional durable worker (needs redis):
docker compose --profile redis --profile worker up --build
```

## Migrations on deploy

```bash
make migrate
# or inside the migrate Compose service / entrypoint with RUN_MIGRATIONS=1
```

Never auto-apply unreviewed AI-generated migrations. Prefer a single migrate job before scaling API replicas.

## Healthchecks

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready   # Neon + Qdrant (+ Redis if not eager)
```

Compose and Dockerfiles probe `/health/live` (API) and `/` (web).

## Known production-readiness gaps (honest)

- Live Neon `usage_limits` / audit migrations may not have been applied in every environment — run `make migrate` with real credentials.
- UsagePolicy process-local counters are not multi-replica safe; workspace Neon caps are the durable control.
- npm/pip audit findings may exist as warnings — review before public launch.
- Optional phases 17–18 (visual understanding, tutor/quiz) are **not** implemented.
- No automatic CDN/WAF/TLS termination in Compose — put a reverse proxy in front for real production.
- Cost estimates are placeholders (`estimate_version=v0-placeholder-not-live-rates`).
- Legal review of privacy/copyright text is still required before public launch (see `infra/deploy/PRIVACY_AND_COMPLIANCE.md`).
