# LearnLens AI

Evidence-grounded learning companion for authorized YouTube / transcript content — playlist notes, hierarchical summaries, and citation-based Q&A.

**Stack:** Next.js (`apps/web`) · FastAPI (`apps/api`) · Neon Postgres · Qdrant Cloud · Redis (local optional)

## Layout

```text
apps/api/          FastAPI service + Dockerfile
apps/web/          Next.js workspace + Dockerfile (scaffold)
packages/contracts Shared types placeholder
infra/             Deploy / infra assets
scripts/           Local helper scripts
tests/             Repo-level smoke tests
fixtures/          Synthetic test fixtures (later)
compose.yaml       Docker Compose (api, web, redis profiles)
```

## Quick start

**Runtimes:** Python 3.12+ via [uv](https://docs.astral.sh/uv/); Node ≥20.19.

```bash
cp .env.example .env   # placeholders only — never commit secrets
make sync
make lint
make test
make help
```

Keep `AI_CHAT_PROVIDER=fake` and `AI_EMBED_PROVIDER=fake` for offline work.

### Docker

```bash
make docker-build                      # build api + web images
docker compose --profile redis up -d   # optional local Redis
docker compose --profile app up --build
```

Neon and Qdrant stay in the cloud — no local database volumes.

## Make targets

| Target | Purpose |
| --- | --- |
| `make help` | List commands |
| `make sync` | Install Python + Node deps |
| `make lint` / `make test` | Offline checks (no paid APIs) |
| `make docker-build` | Build container images |
| `make down` | Stop Compose services |
