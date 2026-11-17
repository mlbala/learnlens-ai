# Cursor Prompt 00 — Project scaffolding and requirements freeze

**Execute in a NEW Cursor Agent chat, using Grok.**

## Purpose and prerequisites
Prerequisite: none. This phase is scoped; the complete design is in `docs/`.

**Read first:** `docs/00_MASTER_DESIGN.md`, `docs/01_SYSTEM_ARCHITECTURE.md`, `docs/10_ADRS.md`, `docs/09_TEST_AND_RELEASE_PLAN.md`.

## Your exact implementation task
Create ONLY the repo's baseline scaffolding and developer commands, without implementing business logic. Validate planned architecture against the design docs and write a brief architecture-freeze note. Structure `apps/web/`, `apps/api/`, `packages/contracts/`, `infra/`, `tests/`, `.github/workflows/`, `scripts/`. Add `.editorconfig`, `.gitignore`, `Makefile`, root README, `.env.example` (placeholders only), Python tooling (`pyproject.toml` using uv or a clearly documented resolver), frontend package manifest and pinned runtime guidance, formatting/lint/type/test defaults. Include GitHub Actions skeleton only if it doesn't require cloud credentials. Preserve `.cursor/` rules, docs and prompts exactly.

## Files and boundaries
- Work only in relevant existing modules; create missing files deliberately. Retain the documented monorepo structure, endpoint names, DB ownership model and stable API contracts.
- This phase must NOT refactor already accepted features outside its scope, silently switch paid providers, change selected embedding dimensions, or start subsequent phases.
- Don't fabricate demo transcript text as actual YouTube content. Mark generated demo data as fixture data.

## Acceptance criteria (must demonstrate)
Repository opens in Cursor; `make help` documents commands; template has no secrets; no operational endpoints yet; minimal sample test and lint run locally or precise missing-tool blocker is noted.

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
