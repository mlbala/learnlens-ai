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
| 09 UI design system | complete | 023eb16 on `dev` | `make lint` / `make typecheck` / `make test` → 138 API passed (4 deselected) + 18 web Vitest passed; `next build` ok; no paid APIs | designer screenshots not captured here — verify `/` and `/design-system` at 375/768/1280 |
| 10 library/playlist/video screens | complete | e4ecede on `dev` | `make lint` / `make typecheck` / `make test` → 139 API passed (4 deselected) + 30 web Vitest passed; `next build` ok; fixture library mode default; no paid APIs | authenticated live API library path optional via `NEXT_PUBLIC_LIBRARY_MODE=api` (requires session); designer screenshots not captured |
| 11 lesson reader + chat | complete | 9a01ff7 on `dev` | `make lint` / `make typecheck` / `make test` → 139 API passed (4 deselected) + 39 web Vitest passed; `next build` ok; fixture lesson/chat default; no paid APIs | designer screenshots at 375/768/1280 optional; API transcript snippet list not yet exposed (fixture snippets only) |
| 12 notes + course synthesis | complete | ea7de36 on `dev` | `make lint` / `make typecheck` / `make test` → 143 API passed (4 deselected) + 41 web Vitest passed; fixture/fake providers only; no paid APIs | optional designer screenshots of playlist course overview at 375/768/1280 |
| 13 guardrails/security | complete | 3ffbbfc on `dev` | `make lint` / `make typecheck` / `uv run pytest … -m "not integration"` → 159 passed (4 deselected); web Vitest → 43 passed; security gate + injection corpus offline; no paid APIs | npm audit advisories pre-existing; live Neon `audit_events` migrate not run; UsagePolicy is process-local |
| 14 eval/testing | complete | 1a32e26 on `dev` | `make lint` / `make typecheck` / `make test` → 164 API passed (4 deselected) + 43 web Vitest; `make eval` → PASS offline (hard gates: citation/leaks/timestamps/schema); no paid APIs | soft quality targets tracked until calibrated; reports under `artifacts/eval/` (gitignored) |
| 15 observability/budgets | complete | fc1f3f2 on `dev` | `make lint` / `make typecheck` / `make test` → 179 API passed (4 deselected) + 44 web Vitest; fake providers only; no paid APIs | live Neon `usage_limits` migrate not run here; sample dashboard is fixture JSON not a live Grafana board |
| 16 CI/deploy/release | complete | 73a2fd1 on `dev` | `make lint` / `make typecheck` / `make test` → 180 API passed (4 deselected) + 44 web; `make smoke-e2e` passed; fake providers only | Docker digests not pinned; live Neon backup drill not run; npm audit advisories remain warnings; do not deploy without operator credentials |
| 17 OPTIONAL visual understanding | complete | 77e0d00 on `dev` | `make lint` / `make typecheck` / `make test` → 189 API passed (4 deselected) + 44 web; fixture media STT/vision offline; no paid APIs; no YouTube downloads | live Neon media migrate not run here; real STT/vision adapters not enabled (fake only) |
| 18 OPTIONAL tutor/quiz/graph | complete | pending commit on `dev` | `make lint` / `make typecheck` / `make test` → 198 API passed (4 deselected) + 47 web Vitest; fake providers only | live Neon `20261120_0009` migrate not run here; no paid APIs; no learning-efficacy claims |

## Per-phase review

- [x] Accepted file scope only; no unrelated rewrite
- [x] `make lint` / `make typecheck` (where available) pass
- [x] Unit/integration tests added and passed
- [ ] Manual workflow observed if UI changes
- [x] No keys, secrets, unauthorized scraping or invented timestamps
- [x] AI calls are mocked by default; no surprise cost
- [x] Commit created or changes ready for review
- [x] Next phase dependencies satisfied
