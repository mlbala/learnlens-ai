# Cursor Prompt 01 — Cloud infrastructure connections and minimal frontend/backend vertical slice

**Execute in a NEW Cursor Agent chat, using Grok.**

## Purpose and prerequisites
Prerequisite: phase 00 accepted and committed. This phase is scoped; the complete design is in `docs/`.

**Read first:** `docs/01_SYSTEM_ARCHITECTURE.md`, `docs/08_DEVOPS_OBSERVABILITY_COST.md`, `docs/10_ADRS.md`.

## Your exact implementation task
Connect to **Neon** (cloud Postgres) and **Qdrant Cloud** instead of running local databases.

Requirements:
- Do **not** add PostgreSQL or Qdrant services to Docker Compose.
- Docker Compose may include only Redis (lightweight) and optional local app containers.
- Settings must load `DATABASE_URL` (Neon), `QDRANT_URL`, and `QDRANT_API_KEY` from the environment.
- FastAPI must expose `/health/live` and `/health/ready` that verify connectivity to Neon and Qdrant Cloud.
- Next.js App Router minimal shell with an API connectivity health indicator.
- Provide a clear `.env.example` documenting the Neon and Qdrant Cloud variables.
- Include short comments or README notes on how to create a free Neon project and free Qdrant Cloud cluster.
- Structured request IDs, CORS exact-origin allowlist, and basic API integration test.

## Files and boundaries
- Work only in relevant existing modules; create missing files deliberately.
- This phase must NOT implement business logic, auth, or later phases.
- Do not make startup calls to paid AI APIs.

## Acceptance criteria (must demonstrate)
App starts locally with only environment variables pointing to free Neon + Qdrant Cloud tiers; health checks succeed against both services; web calls backend health endpoint; no local database volumes are required.

## End-of-phase required output
Provide paths, test evidence, security notes and one reproducible manual verification command or sequence; update `checklists/PHASE_TRACKER.md` for this phase only.

## Execution contract for Cursor Agent / Grok
- Act as a senior staff engineer. **Implement only this phase**.
- Read `AGENTS.md`, `.cursor/rules/*.mdc` and the named docs first.
- Start with a short implementation plan, then make scoped changes.
- Python 3.12+, type hints, Pydantic v2; TypeScript strict.
- Use fake providers by default. No paid network calls unless explicitly requested.
- At the end, respond with: **implemented**, **files changed**, **tests and results**, **manual verification**, **risks/blockers**, **next phase**, and **suggested git commit message**. Then **STOP**.
