# 09 — Automated Test Plan and Release Gates

## 1. Testing pyramid

**Unit (most):** YouTube URL canonicalizer, timecode parsers, segmenters, chunk mappings, schemas, provider mapper, Qdrant filters, budgets, auth service. **Integration:** Postgres migrations, Redis/Celery worker tasks, Qdrant collection, API endpoints with fake provider. **E2E:** register/login -> add YouTube metadata -> attach synthetic authorized SRT -> worker -> video chapter/summary -> grounded chat -> playlist summary; repeat for missing transcript. **Security:** attack payload fixture matrix. **Live vendor smoke (opt-in):** one real provider text request, one embedding, one official YouTube metadata lookup, never on every PR.

## 2. Exact mandatory invariants

- I01: No public URL-only video marked transcript-analyzed without a permitted source asset.
- I02: A playlist of 4 items with 2 ready yields `coverage_ratio=0.5`, and synthesis excludes other two.
- I03: Plain TXT source has no generated timestamp or source-time link.
- I04: Every model-cited segment ID belongs to authenticated workspace, active source revision, query scope, and retrieved evidence packet.
- I05: If evidence is absent, output says unsupported/not covered; do not make up an answer.
- I06: Workspace A cannot access B video, playlist, source, job, chat or Qdrant candidate, including guessed UUIDs.
- I07: Repeated identical upload yields one content revision/index manifest, no duplicate processing.
- I08: Switching text provider does not mutate embedding profile or vector collection.
- I09: Embedding dimension change cannot append vectors into an incompatible collection.
- I10: Raw transcript text and keys never appear in standard operational logs.
- I11: All failure states have readable UI and retry only where permitted.
- I12: No unauthorized YouTube downloading/scraping code in application core.

## 3. Golden fixtures

Create 6 **synthetic** transcripts with explicit licensing note, deterministic stable mock video IDs: `comm_good.vtt`, `python_course_01.srt`, `python_course_02.srt`, `untimed.txt`, `malicious_prompt.vtt`, `multilingual_excerpt.vtt`. Keep <=2 minutes each to minimize test costs. Add `expected.jsonl` with question, scope, expected evidence span IDs, answer key phrases, should_abstain and no_timestamps flag. Keep a playlist with two ready and one missing sources.

## 4. Gate by phase

| Gate | Required evidence |
| --- | --- |
| G0 setup | `make format`, `make lint`, `make test` and compose health local |
| G1 sources | valid metadata and honest missing transcript, all URL/parser tests |
| G2 summaries | valid JSON, normalized provenance, 2-video playlist coverage |
| G3 RAG | tenant filtering, target citation validity 100%, abstention tests |
| G4 UX | desktop/tablet/mobile screenshots, axe checks, keyboard nav |
| G5 security | all negative access tests, injection corpus, CSRF, upload abuse |
| G6 release | CI green, backup/restore demo, quotas, provider smoke if configured |

**Important:** numerical targets in research doc are *proposed test acceptance goals*. If eval fails, present actual results; don't fake score or mark gate passed. Human review is required for entailment, educational usefulness and visual quality.

## 5. Testing commands target

The development prompts should standardize these command names and keep them working throughout:

```bash
make dev
make migrate
make format
make lint
make typecheck
make test
make test-integration
make smoke
make down
```

Optional `make test-e2e` and `make provider-smoke` require separate explicit opt-in. `make clean` must never delete persistent data without a confirmation guard.

## 6. Definition of done for every Cursor phase

Code and docs changed only inside requested scope; new paths documented; tests authored and run; static checks pass or blockers explicitly declared; acceptance checklist complete; no fake integration claims; no swallowed exceptions; no placeholder buttons or unbounded AI loops; ready for a small Git commit.
