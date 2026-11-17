# Cursor Phase Tracker

Update after **each** Cursor Agent phase. Do not mark complete if tests did not run. One phase per fresh chat; one git commit after verified acceptance.

| Phase | Status | Commit | Tests run / outcome | Blockers |
| --- | --- | --- | --- | --- |
| 00 project setup | not started | | | |
| 01 infra + vertical slice | not started | | | |
| 02 data + auth | not started | | | |
| 03 provider adapters | not started | | | |
| 04 YouTube metadata | not started | | | |
| 05 authorized transcript ingestion | not started | | | |
| 06 normalization + summaries | not started | | | |
| 07 Qdrant indexing/search | not started | | | |
| 08 grounded QA | not started | | | |
| 09 UI design system | not started | | | |
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

- [ ] Accepted file scope only; no unrelated rewrite
- [ ] `make lint` / `make typecheck` (where available) pass
- [ ] Unit/integration tests added and passed
- [ ] Manual workflow observed if UI changes
- [ ] No keys, secrets, unauthorized scraping or invented timestamps
- [ ] AI calls are mocked by default; no surprise cost
- [ ] Commit created or changes ready for review
- [ ] Next phase dependencies satisfied
