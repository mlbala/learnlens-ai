# Cursor Prompt 16 — Build, test, deploy and handoff production checklist

**Execute in a NEW Cursor Agent chat, using Grok.**

## Purpose and prerequisites
Prerequisite: phase 15 accepted and committed. This phase is scoped; the complete design is in `docs/`.

**Read first:** `docs/08_DEVOPS_OBSERVABILITY_COST.md`, `docs/09_TEST_AND_RELEASE_PLAN.md`, `docs/06_SECURITY_GUARDRAILS.md`.

## Your exact implementation task
Add stable Docker images for web/API/worker, Compose production-like sample with secrets supplied externally, migrations on deploy, healthchecks, CI workflows for lint/type/tests/migration checks/security deps and build, documented configuration, backup/restore steps and incident playbook. Add local end-to-end smoke for example video, partial playlist and adversarial transcript using fake providers. Include privacy/copyright disclaimer, official YouTube compliance caveat, dependency license inventory and deployment guide. Do not actually deploy without permission and credentials.

## Files and boundaries
- Work only in relevant existing modules; create missing files deliberately. Retain the documented monorepo structure, endpoint names, DB ownership model and stable API contracts.
- This phase must NOT refactor already accepted features outside its scope, silently switch paid providers, change selected embedding dimensions, or start subsequent phases.
- Don't fabricate demo transcript text as actual YouTube content. Mark generated demo data as fixture data.

## Acceptance criteria (must demonstrate)
Fresh clone local run verified; CI gates configured and run where possible; no secrets committed; end-to-end demo with fixture data; known production readiness gaps documented honestly.

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
