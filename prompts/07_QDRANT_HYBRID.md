# Cursor Prompt 07 — Qdrant Cloud indexing and workspace-isolated hybrid retrieval

**Execute in a NEW Cursor Agent chat, using Grok.**

## Purpose and prerequisites
Prerequisite: phase 06 accepted and committed. This phase is scoped; the complete design is in `docs/`.

**Read first:** `docs/05_RAG_SUMMARIZATION_AND_EVAL.md`, `docs/02_DATA_AND_API_CONTRACTS.md`, `docs/03_AI_PROVIDER_ROUTING.md`, `docs/10_ADRS.md`.

## Your exact implementation task
Implement embedding profile manifest, dimension verification via fake/single known vectors, and Qdrant Cloud collection creation per model/dim/version.

Requirements:
- Connect exclusively to **Qdrant Cloud** using `QDRANT_URL` + `QDRANT_API_KEY`.
- Chunk index/upsert/delete by stable IDs and revisions.
- Payload must include `workspace_id`, `video_id`, `segment_ids`, `source_revision`, verified timing, and provenance.
- Implement named dense retrieval plus a Qdrant-compatible BM25/sparse lexical path and RRF fusion.
- Dense-only fallback must be an explicit feature flag, not silent.
- Query service resolves authorized video IDs in Neon (SQL) and always adds Qdrant tenant/scope filters.
- Safe reindex contract for embedding profile/dimension changes (never mix dimensions).
- Source of truth remains Neon Postgres; Qdrant is derived only.
- Document free-tier capacity expectations (1 GB RAM / 4 GB disk) and graceful degradation.

## Files and boundaries
- Work only in relevant existing modules.
- This phase must NOT refactor already accepted features outside its scope or start subsequent phases.
- Don't fabricate demo transcript text as actual YouTube content.

## Acceptance criteria (must demonstrate)
Fake embedding index/search tests; cross-tenant search cannot retrieve another workspace; filter escaping tests; wrong dimensions rejected; dense+lexical hits fused with contract tested; deletes remove indexed points from Qdrant Cloud; free-tier connection succeeds.

## End-of-phase required output
Provide paths, test evidence, security notes and one reproducible manual verification command or sequence; update `checklists/PHASE_TRACKER.md` for this phase only.

## Execution contract for Cursor Agent / Grok
- Act as a senior staff engineer. **Implement only this phase**.
- Read `AGENTS.md`, `.cursor/rules/*.mdc` and the named docs first.
- Start with a short implementation plan.
- Python 3.12+, type hints, Pydantic v2.
- Use **fake AI and fixture data by default**.
- At the end, respond with: **implemented**, **files changed**, **tests and results**, **manual verification**, **risks/blockers**, **next phase**, and **suggested git commit message**. Then **STOP**.
