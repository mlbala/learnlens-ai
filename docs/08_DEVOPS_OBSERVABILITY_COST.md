# 08 — DevOps, Observability and Cost Controls

## Environments

- **Local development:** Next.js + FastAPI on the developer machine. Redis via Docker Compose (lightweight).  
  **Neon** (cloud Postgres) and **Qdrant Cloud** (free tier) are the only data stores.
- **CI:** Uses fake providers and in-memory or test doubles where possible. Neon and Qdrant Cloud free tiers can be used for integration tests if credentials are provided as secrets.
- **Production:** Same topology — Neon + Qdrant Cloud (or upgraded tiers) + containerized API/worker + optional Vercel for the web frontend.

## Free-tier limits (development)

| Service | Free tier (approx.) | Idle behavior | Notes |
|---------|---------------------|---------------|-------|
| Neon | ~1 GB storage per project | Scales to zero after idle | Generous for development |
| Qdrant Cloud | 0.5 vCPU / 1 GB RAM / 4 GB disk | Suspended after ~1 week; deleted after ~4 weeks if not reactivated | Monitor usage; re-activate periodically |
| Redis | Local Docker or free cloud option | — | Keep small |

## Required environment variables

```bash
DATABASE_URL=postgresql://...@ep-xxx.neon.tech/neondb?sslmode=require
QDRANT_URL=https://xxx.cloud.qdrant.io
QDRANT_API_KEY=...
REDIS_URL=redis://localhost:6379
```

## Observability

- Structured logging with request IDs.
- Health endpoints that check Neon and Qdrant Cloud connectivity.
- OpenTelemetry instrumentation hooks (phase 15).
- Cost tracking table for LLM provider usage (`provider_runs`).
- Simple dashboard or admin view showing current free-tier headroom when possible.

## Cost controls

- Default to fake providers until explicitly switched.
- Per-workspace usage limits enforced in Neon.
- No automatic paid API calls on startup or in background jobs unless configured.
- Document expected embedding and chat costs before enabling live providers.

## Deployment notes

- No local database volumes in any environment.
- Secrets only via environment variables or a secrets manager.
- Document Neon and Qdrant Cloud project/cluster creation steps in the main README.
