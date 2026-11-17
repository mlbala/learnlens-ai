# Architecture freeze — phase 00

**Date:** 2026-11-17  
**Status:** frozen for implementation sequence 00→16 (optional 17–18)

Validated against `docs/00_MASTER_DESIGN.md`, `docs/01_SYSTEM_ARCHITECTURE.md`, `docs/10_ADRS.md`, and `docs/09_TEST_AND_RELEASE_PLAN.md`.

## Locked decisions

| Area | Freeze |
| --- | --- |
| Topology | Modular monolith: Next.js `apps/web`, FastAPI `apps/api`, Celery worker (later), Redis local/cloud |
| Source of truth | Neon Postgres (ownership, transcripts, jobs, citations) |
| Search index | Qdrant Cloud hybrid (derived only; tenant filters required) |
| Text models | OpenAI / Gemini / DeepSeek adapters; default `AI_CHAT_PROVIDER=fake` |
| Embeddings | OpenAI / Gemini only; independent of chat provider; default `AI_EMBED_PROVIDER=fake` |
| Auth | First-party session auth (Argon2id) for local reproducibility (ADR-009) |
| Citations | Server-validated evidence IDs only (ADR-007) |
| Ingestion | Metadata via official YouTube Data API; authorized SRT/VTT/TXT only — no scrapers/downloads |
| Frontend | Formal enterprise UI (ADR-008); TypeScript strict |
| Tooling | Python 3.12+ / Pydantic v2 via uv; Node ≥20.19 for web workspaces |

## Explicit non-goals (MVP)

- Guaranteed transcripts from arbitrary public YouTube URLs
- Unauthorized media/caption scraping or download bypasses
- Microservices split, local Postgres/Qdrant volumes, or paid API calls in default tests

## Phase 00 boundary

Phase 00 freezes structure, tooling, and the decisions above. Business domains (auth, ingestion, RAG, chat) remain out of scope until their numbered phases. Default tests stay offline with `AI_*_PROVIDER=fake`.

Conflicts: none found between the named docs and this freeze. Safer choice if future prompts diverge: fail closed on permissions/evidence and keep fake providers as the offline default.
