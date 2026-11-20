# Cursor Phase Tracker

Update after **each** Cursor Agent phase. Do not mark complete if tests did not run. One phase per fresh chat; one git commit after verified acceptance.

| Phase | Status | Commit | Tests run / outcome | Blockers |
| --- | --- | --- | --- | --- |
| 00 project setup | complete | 8795901 scaffold; 54c8c5e docs restore | `make help` / `make lint` / `make typecheck` / `make test` → 12 passed offline | concurrent main also contains phase-01 health slice (`4ccdb14`) |
| 01 infra + vertical slice | present on main (concurrent) | 4ccdb14 | offline health tests in tree; not re-validated in phase-00 chat | out of scope for phase-00 request |
| 02 data + auth | complete | fd4991c on `dev/phase-02-data-auth` | `make lint` / `make typecheck` / `make test` → 21 passed offline (auth, CSRF, IDOR, migration structure); 2 integration deselected | live Neon Alembic upgrade/downgrade not executed here (avoid destructive reset); run `make migrate` when ready |
| 03 provider adapters | complete | 92d215d on `dev` | `make lint` / `make typecheck` / `make test` → 50 passed offline (fake + mocked OpenAI/Gemini/DeepSeek text, OpenAI/Gemini embeddings, settings/providers, 401/429/timeout/refusal/dimension); 2 integration deselected | no live/paid provider calls; PUT `/settings/providers` deferred to later phase |
| 04 YouTube metadata | complete | b090616 on `dev` | `make lint` / `make typecheck` / `make test` → 84 passed offline (URL/SSRF, fixture video/playlist import, multi-page order + unavailable items, idempotency, never summarized); 2 integration deselected | no live YouTube Data API calls; official client present but default provider is fake |
| 05 authorized transcript ingestion | complete | c4504e2 on `dev` | `make lint` / `make typecheck` / `make test` → 102 passed offline (SRT/VTT exact ms, TXT null timestamps, 413/attestation/tenant, eager worker retries + idempotency); 2 integration deselected | no Redis required (CELERY_TASK_ALWAYS_EAGER); no paid APIs; media/ASR not implemented by design |
| 06 normalization + summaries | complete | cc69c28 on `dev` | `make lint` / `make typecheck` / `make test` → 116 passed offline (chunker, evidence gate, chapters/summaries, cache, blocked-no-transcript, injection-as-data); 2 integration deselected | no paid AI calls; Qdrant indexing deferred to phase 07 |
| 07 Qdrant indexing/search | complete | 12403da on `dev` | `make lint` / `make typecheck` / `make test` → 126 passed offline (fake hybrid index/search, tenant filters, RRF, dimension reject, deletes); 4 integration deselected | no paid AI calls; live Qdrant free-tier upsert optional via `test_qdrant_integration` |
| 08 grounded QA | complete | 0029bc8 on `dev` | `make lint` / `make typecheck` / `make test` → 138 passed offline (timed cites, invented citation reject, TXT no t=, tenant 404, abstention); 4 integration deselected | no paid AI calls; chat index still caller/test-driven via memory store (ingest→index hook remains later) |
| 09 UI design system | complete | on `dev` (see session commit) | `make lint` / `make typecheck` / `make test` → 138 API passed (4 deselected) + 18 web Vitest passed; `next build` ok; no paid APIs | designer screenshots not captured here — verify `/` and `/design-system` at 375/768/1280 |
| 10 library/playlist/video screens | not started | | | |
| 11 lesson reader + chat | not started | | | |
| 12 notes + course synthesis | not started | | | |
| 13 guardrails/security | not started | | | |
| 14 eval/testing | not started | | | |
| 15 observability/budgets | not started | | | |
| 16 CI/deploy/release | not started | | | |
| 17 OPTIONAL visual understanding | not started | | | |
| 18 OPTIONAL tutor/quiz/graph | not started | | | |

## Per-phase review

- [x] Accepted file scope only; no unrelated rewrite
- [x] `make lint` / `make typecheck` (where available) pass
- [x] Unit/integration tests added and passed
- [ ] Manual workflow observed if UI changes
- [x] No keys, secrets, unauthorized scraping or invented timestamps
- [x] AI calls are mocked by default; no surprise cost
- [x] Commit created or changes ready for review
- [x] Next phase dependencies satisfied
