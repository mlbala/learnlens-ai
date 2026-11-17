# 01 — System Architecture and Runtime Flows

## 1. C4-style context

**Actors:** learner, creator/authorized content owner, operator.  
**External systems:** YouTube Data API, selected LLM API (OpenAI/Gemini/DeepSeek), selected embedding API, Neon (Postgres), Qdrant Cloud.  
**Internal:** Next.js web, FastAPI app, Redis (local or cloud), Celery worker.

```
                      ┌───────────────────────┐
  Learner / owner ────>│ Next.js web          │
                      │ Auth-aware web UI     │
                      └───────────┬───────────┘
                                  │ same-origin /api proxy
                      ┌───────────▼───────────┐
                      │ FastAPI              │
                      │ Auth / ownership     │──► YouTube Data API (metadata only)
                      │ Playlists / videos   │
                      │ Content / Chat       │──► OpenAI / Gemini / DeepSeek (text)
                      │ Budget / audit       │
                      └───┬────────┬─────────┘
                          │        │
                 ┌────────▼──┐  ┌──▼──────────┐
                 │ Neon      │  │ Redis      │
                 │ Postgres  │  │ (local/    │
                 │ (cloud)   │  │  cloud)    │
                 └───────────┘  └──┬─────────┘
                                   │
                           ┌───────▼──────────┐
                           │ Worker           │──► Provider APIs
                           │ normalize        │──► Embedding API
                           │ summarize/index  │──► Qdrant Cloud
                           └──────────────────┘
```

**Crucial:** Qdrant Cloud is a derived search index, not the authority for ownership, source text, timecodes, deletion or job state. Neon Postgres stores normalized evidence segments and identity. Free-tier limits apply to both Neon and Qdrant Cloud.

## 2. Runtime containers / services

- `web`: Next.js App Router, server-side route/proxy to FastAPI. Never expose provider secrets in `NEXT_PUBLIC_*`.
- `api`: FastAPI, Pydantic models, user authentication, metadata HTTP client and grounded Q&A. Connects to Neon and Qdrant Cloud via environment variables.
- `worker`: Celery processes specific tasks with hard time limits, heartbeats and a bounded concurrency; **no** recursive open-ended agent loops.
- `redis`: Celery broker and cache (local Docker is fine; free cloud Redis is also acceptable). Never sole source of truth for job status.
- **Neon**: cloud Postgres (free tier). Holds all relational data, ownership, transcripts, jobs, and citations.
- **Qdrant Cloud**: free-tier cluster. Holds only derived vector index with tenant filters.
- Local Docker Compose is used only for Redis and optionally the app processes themselves. No local Postgres or Qdrant volumes.

## 3. Repository architecture (implementation output)

```
learnlens-ai/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── api/v1/
│   │   │   ├── core/              # settings, security, observability
│   │   │   ├── domain/
│   │   │   ├── db/                # SQLAlchemy + Alembic (targets Neon)
│   │   │   ├── services/
│   │   │   ├── ai/providers/
│   │   │   ├── ai/prompts/
│   │   │   ├── ai/retrieval/      # Qdrant Cloud hybrid
│   │   │   └── workers/
│   │   └── tests/
│   └── web/
│       ├── app/
│       ├── components/
│       ├── features/
│       ├── lib/
│       └── tests/
├── infra/
├── fixtures/
├── scripts/
├── docs/
├── .cursor/rules/
├── compose.yaml                  # Redis + optional app only
├── Makefile
├── .env.example                  # DATABASE_URL (Neon), QDRANT_URL, QDRANT_API_KEY
└── README.md
```

## 4. Key environment variables

```bash
DATABASE_URL=postgresql://...@ep-xxx.neon.tech/neondb?sslmode=require
QDRANT_URL=https://xxx.cloud.qdrant.io
QDRANT_API_KEY=...
REDIS_URL=redis://localhost:6379
AI_CHAT_PROVIDER=fake
AI_EMBED_PROVIDER=fake
```

## 5. Free-tier operational notes

- Neon free tier: ~1 GB storage per project; projects may scale to zero after idle.
- Qdrant Cloud free tier: 0.5 vCPU / 1 GB RAM / 4 GB disk; clusters can be suspended after ~1 week of inactivity and deleted after ~4 weeks if not reactivated.
- Monitor usage in both dashboards during development.
- Prefer fake embedding providers until retrieval quality is validated.
