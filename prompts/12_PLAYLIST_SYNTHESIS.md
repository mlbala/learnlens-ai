# Cursor Prompt 12 — Course-level summary and reusable learning notes

**Execute in a NEW Cursor Agent chat, using Grok.**

## Purpose and prerequisites
Prerequisite: phase 11 accepted and committed. This phase is scoped; the complete design is in `docs/`.

**Read first:** `docs/05_RAG_SUMMARIZATION_AND_EVAL.md`, `docs/04_INGESTION_AND_COMPLIANCE.md`, `docs/07_UI_UX_DESIGN_SYSTEM.md`.

## Your exact implementation task
Implement playlist synthesis worker combining only ready per-video summaries into grouped topic modules, a curriculum/learning map, cross-video concepts, redundant-topic grouping and key takeaways with source IDs. Persist included/excluded video sets, source revisions, counts and `partial` vs `complete`; invalidate synthesis when input revision or membership changes; reuse per-video cached summaries. Add course overview and notes UI; safe Markdown export (optional, only if cheap), no invented coverage of missing lessons.

## Files and boundaries
- Work only in relevant existing modules; create missing files deliberately. Retain the documented monorepo structure, endpoint names, DB ownership model and stable API contracts.
- This phase must NOT refactor already accepted features outside its scope, silently switch paid providers, change selected embedding dimensions, or start subsequent phases.
- Don't fabricate demo transcript text as actual YouTube content. Mark generated demo data as fixture data.

## Acceptance criteria (must demonstrate)
Playlist 3/5 transcripts yields explicit 3/5 partial summary; changed source invalidates summary; second unchanged run reuses cached video results; each learning claim maps to included video evidence.

## End-of-phase required output
Provide paths, test evidence, security notes and one reproducible manual verification command or sequence; update `checklists/PHASE_TRACKER.md` for this phase only, preserving any earlier records.

## Execution contract for Cursor Agent / Grok
- Act as a senior staff engineer. **Implement only this phase**, not future phases; use the existing workspace and preserve accepted prior work.
- Read `AGENTS.md`, `.cursor/rules/*.mdc` and the specific documents named above before coding. The docs are requirements; if they conflict, explain the conflict and choose the safer design rather than silently changing scope.
- Start by inspecting current files and reporting a 4–8 item implementation plan. Make changes in small patches; do not rewrite unrelated files.
- Python 3.12+, type hints and Pydantic v2; TypeScript strict. Fail closed on permissions and evidence. No unauthorized YouTube media scraping/downloads.
- Use **fake AI and fixture data by default**: do not incur provider charges, perform paid network calls, reset databases, deploy, or edit secrets without the operator explicitly requesting it.
- Add executable, deterministic tests for new behavior including negative cases. Run the relevant unit tests, typechecks and lint commands that are available; report exact commands and results. If services are unavailable, identify what was not tested instead of claiming success.
- Never expose secrets, raw user transcripts in logs, model chain-of-thought, or arbitrary generated timestamp links. Add audit-safe error handling.
- At the end, respond with: **implemented**, **files changed**, **tests and results**, **manual verification**, **risks/blockers**, **next phase**, and **suggested git commit message**. Then **STOP**. Don't automatically start the next phase.
