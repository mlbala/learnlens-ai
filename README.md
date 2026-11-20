# LearnLens AI

Evidence-grounded learning companion for authorized YouTube / transcript content — playlist notes, hierarchical summaries, and citation-based Q&A.

**Stack:** Next.js (`apps/web`) · FastAPI (`apps/api`) · Celery worker · Neon Postgres · Qdrant Cloud · Redis (local optional)

**Design package:** [`START_HERE_IN_CURSOR.md`](START_HERE_IN_CURSOR.md) · [`docs/`](docs/) · [`prompts/`](prompts/) · [`docs/ARCHITECTURE_FREEZE.md`](docs/ARCHITECTURE_FREEZE.md) · [`AGENTS.md`](AGENTS.md)

## Layout

```text
apps/api/          FastAPI + Celery worker image + Dockerfile
apps/web/          Next.js App Router + Dockerfile
packages/contracts Shared types placeholder
infra/deploy/      Deployment, backup/restore, incident, privacy docs
infra/licenses/    Dependency license inventory
infra/observability/  Health/cost runbook + sample dashboard
scripts/           Local helper scripts (layout, licenses)
tests/             Repo-level smoke tests
fixtures/          Synthetic fixture data (not real YouTube captions)
compose.yaml       Local Compose (api, web, worker, redis profiles)
compose.prod.yaml  Production-like sample (external secrets; no deploy by default)
```

## Privacy, copyright, YouTube compliance

Users must attest rights before transcript upload. Public YouTube URLs do **not** grant caption access. No unofficial scraping or media downloaders. See [`infra/deploy/PRIVACY_AND_COMPLIANCE.md`](infra/deploy/PRIVACY_AND_COMPLIANCE.md) and [`docs/04_INGESTION_AND_COMPLIANCE.md`](docs/04_INGESTION_AND_COMPLIANCE.md). Fixture files under `fixtures/` are synthetic demo data only.

## Cloud data stores (required)

LearnLens does **not** run Postgres or Qdrant in Docker. Use free cloud tiers:

### Neon (Postgres)

1. Create a project at [console.neon.tech](https://console.neon.tech).
2. Copy the **pooled** connection string → `DATABASE_URL`.
3. Copy the **direct** connection string → `DATABASE_URL_UNPOOLED` (migrations).
4. Free tier is ~1 GB storage; projects may scale to zero when idle.

### Qdrant Cloud

1. Create a free cluster at [cloud.qdrant.io](https://cloud.qdrant.io).
2. Copy the HTTPS endpoint → `QDRANT_URL` and the API key → `QDRANT_API_KEY`.
3. Free tier (~0.5 vCPU / 1 GB RAM / 4 GB disk) may suspend after ~1 week idle; reactivate before deletion (~4 weeks).

## Quick start (fresh clone)

**Runtimes:** Python 3.12+ via [uv](https://docs.astral.sh/uv/); Node ≥20.19.

```bash
cp .env.example .env   # fill Neon + Qdrant values; never commit secrets
make sync
make lint
make typecheck
make test              # offline unit + e2e smoke (fake providers)
make smoke-e2e         # fixture video / partial playlist / adversarial VTT
make test-integration  # optional: real Neon/Qdrant readiness when creds are set
```

Keep `AI_CHAT_PROVIDER=fake`, `AI_EMBED_PROVIDER=fake`, and `YOUTUBE_METADATA_PROVIDER=fake` for offline work.

### Local vertical slice

```bash
# Terminal 1 — API (loads DATABASE_URL / QDRANT_* from .env)
make migrate           # once credentials exist
make dev

# Terminal 2 — web shell
npm run dev --workspace=@learnlens/web

# Checks
curl -s http://127.0.0.1:8000/health/live
curl -s http://127.0.0.1:8000/health/ready
# Browser: http://localhost:3000  (health indicator via /api/backend-health)
```

### Docker

```bash
make docker-build
docker compose --profile redis up -d   # optional local Redis
docker compose --profile app up --build
# Durable worker (requires redis profile):
docker compose --profile redis --profile worker up --build
```

Production-like sample (secrets from environment only — **do not deploy without permission**):

```bash
# export DATABASE_URL QDRANT_* SESSION_SECRET ...
docker compose -f compose.prod.yaml config   # validate
# docker compose -f compose.prod.yaml up --build   # operator-only
```

See [`infra/deploy/DEPLOYMENT.md`](infra/deploy/DEPLOYMENT.md), [`infra/deploy/BACKUP_RESTORE.md`](infra/deploy/BACKUP_RESTORE.md), [`infra/deploy/INCIDENT_PLAYBOOK.md`](infra/deploy/INCIDENT_PLAYBOOK.md).

Neon and Qdrant stay in the cloud — no local database volumes.

## Make targets

| Target | Purpose |
| --- | --- |
| `make help` | List commands |
| `make sync` | Install Python + Node deps |
| `make lint` / `make typecheck` / `make test` | Offline checks (mocked probes; no paid AI) |
| `make smoke-e2e` | Offline fixture e2e smoke |
| `make test-integration` | Real Neon + Qdrant readiness when env is set |
| `make migrate` | Alembic upgrade head (Neon) |
| `make audit` / `make licenses` | Dependency vuln scan / license inventory |
| `make docker-build` | Build container images (api/worker + web) |
| `make down` | Stop Compose services |
