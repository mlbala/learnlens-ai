# Cursor Prompt 04 — YouTube URL validation, video import and playlist metadata enumeration

**Execute in a NEW Cursor Agent chat, using Grok.**

## Purpose and prerequisites
Prerequisite: phase 03 accepted and committed. This phase is scoped; the complete design is in `docs/`.

**Read first:** `docs/04_INGESTION_AND_COMPLIANCE.md`, `docs/02_DATA_AND_API_CONTRACTS.md`, `docs/06_SECURITY_GUARDRAILS.md`.

## Your exact implementation task
Implement strict parser for video, shorts, shortened and playlist URLs with allowlisted HTTPS hostname and exact video/list ID rules. **Never fetch the user-supplied URL**; construct outbound calls only to the official YouTube Data API. Add official API metadata adapters with offline fakes; video/playlist import endpoints; playlist pagination (max 50 per page), capped total imports, positional ordering, idempotency, unavailable/private/deleted cases, quota error handling and caching subject to provider policies. Persist `metadata_only`, `needs_transcript`, `unavailable` states. In UI/API be clear that pasted public video URLs do not grant transcript access.

## Files and boundaries
- Work only in relevant existing modules; create missing files deliberately. Retain the documented monorepo structure, endpoint names, DB ownership model and stable API contracts.
- This phase must NOT refactor already accepted features outside its scope, silently switch paid providers, change selected embedding dimensions, or start subsequent phases.
- Don't fabricate demo transcript text as actual YouTube content. Mark generated demo data as fixture data.

## Acceptance criteria (must demonstrate)
Malicious URL and SSRF parser tests pass; metadata imports work from fixtures; multi-page playlist with missing items preserves order; re-import is idempotent; import never falsely marks video summarized.

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
