# LearnLens AI

Evidence-grounded learning companion for authorized YouTube / transcript content — playlist notes, hierarchical summaries, and citation-based Q&A.

**Stack:** Next.js (`apps/web`) · FastAPI (`apps/api`) · Neon Postgres · Qdrant Cloud · Redis (local optional)

## Layout

```text
apps/api/          FastAPI service + Dockerfile
apps/web/          Next.js App Router + health indicator
packages/contracts Shared types placeholder
infra/             Deploy / infra assets
scripts/           Local helper scripts
tests/             Repo-level smoke tests
fixtures/          Synthetic test fixtures (later)
compose.yaml       Docker Compose (api, web, redis profiles — no local DBs)
```

## Cloud data stores (required)

LearnLens does **not** run Postgres or Qdrant in Docker. Use free cloud tiers:

### Neon (Postgres)

1. Create a project at [console.neon.tech](https://console.neon.tech).
2. Copy the **pooled** connection string → `DATABASE_URL`.
3. Copy the **direct** connection string → `DATABASE_URL_UNPOOLED` (migrations in phase 02+).
4. Free tier is ~1 GB storage; projects may scale to zero when idle.

### Qdrant Cloud

1. Create a free cluster at [cloud.qdrant.io](https://cloud.qdrant.io).
2. Copy the HTTPS endpoint → `QDRANT_URL` and the API key → `QDRANT_API_KEY`.
3. Free tier (~0.5 vCPU / 1 GB RAM / 4 GB disk) may suspend after ~1 week idle; reactivate before deletion (~4 weeks).

## Quick start

**Runtimes:** Python 3.12+ via [uv](https://docs.astral.sh/uv/); Node ≥20.19.

```bash
cp .env.example .env   # fill Neon + Qdrant values; never commit secrets
make sync
make lint
make test
make test-integration  # optional: real Neon/Qdrant readiness when creds are set
```

Keep `AI_CHAT_PROVIDER=fake` and `AI_EMBED_PROVIDER=fake` for offline work.

### Local vertical slice

```bash
# Terminal 1 — API (loads DATABASE_URL / QDRANT_* from .env)
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
docker compose --profile redis up -d   # optional local Redis only
docker compose --profile app up --build
```

Neon and Qdrant stay in the cloud — no local database volumes.

## Make targets

| Target | Purpose |
| --- | --- |
| `make help` | List commands |
| `make sync` | Install Python + Node deps |
| `make lint` / `make test` | Offline checks (mocked probes; no paid AI) |
| `make test-integration` | Real Neon + Qdrant readiness when env is set |
| `make dev` | Run FastAPI with reload |
| `make docker-build` | Build container images |
| `make down` | Stop Compose services |
