# Cursor Prompt 08 — Evidence-grounded RAG chat with verified timestamp citations

**Execute in a NEW Cursor Agent chat, using Grok.**

## Purpose and prerequisites
Prerequisite: phase 07 accepted and committed. This phase is scoped; the complete design is in `docs/`.

**Read first:** `docs/05_RAG_SUMMARIZATION_AND_EVAL.md`, `docs/02_DATA_AND_API_CONTRACTS.md`, `docs/06_SECURITY_GUARDRAILS.md`.

## Your exact implementation task
Implement authorized video/playlist/library chat thread APIs; retrieve bounded Qdrant candidates, fetch source segments from Postgres and construct evidence packet with stable IDs. Use structured response from text adapter with claims and citation_segment_ids. Server validate every claim's references subset of retrieved allowed evidence, current revision and tenant; reject or qualify unsupported claims, provide source-coverage refusal. Build timestamp URLs server-side only from verified original milliseconds and sanitized video ID. For plain TXT links omit timestamp. Persist threaded messages, scoped citations and minimal run usage. Provide 'simple','standard','technical' explanation style; explicitly label AI-generated analogies.

## Files and boundaries
- Work only in relevant existing modules; create missing files deliberately. Retain the documented monorepo structure, endpoint names, DB ownership model and stable API contracts.
- This phase must NOT refactor already accepted features outside its scope, silently switch paid providers, change selected embedding dimensions, or start subsequent phases.
- Don't fabricate demo transcript text as actual YouTube content. Mark generated demo data as fixture data.

## Acceptance criteria (must demonstrate)
Answer with known timed evidence cites correct video/segment/time; model-invented citation rejected; plain TXT never produces t= link; wrong-tenant thread inaccessible; insufficient evidence yields honest refusal.

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
