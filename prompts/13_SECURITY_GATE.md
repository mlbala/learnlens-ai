# Cursor Prompt 13 — Defense-in-depth AI guardrails and adversarial security audit

**Execute in a NEW Cursor Agent chat, using Grok.**

## Purpose and prerequisites
Prerequisite: phase 12 accepted and committed. This phase is scoped; the complete design is in `docs/`.

**Read first:** `docs/06_SECURITY_GUARDRAILS.md`, `docs/09_TEST_AND_RELEASE_PLAN.md`, `docs/04_INGESTION_AND_COMPLIANCE.md`.

## Your exact implementation task
Audit prior code against security design and fix only concrete vulnerabilities. Add identity/tenant policies, CSRF/SSRF validation, secure cookies/headers, upload content validation, input sizes and quotas, injection-safe SQL, output escaping, OWASP-relevant web controls and least privilege. Add transcript/tool-result prompt injection test corpus ('ignore instructions', forged roles, encoded payloads, URLs, secret exfiltration, unsupported claims); trust-boundary delimiting, citation allowlist and deterministic post-validation are mandatory. Add output PII minimization where appropriate, abuse/rate controls, auditable decisions and secret redaction in logging/tracing. Pin and audit dependencies. Guardrails are multilayered; don't claim any library guarantees 100% attack prevention.

## Files and boundaries
- Work only in relevant existing modules; create missing files deliberately. Retain the documented monorepo structure, endpoint names, DB ownership model and stable API contracts.
- This phase must NOT refactor already accepted features outside its scope, silently switch paid providers, change selected embedding dimensions, or start subsequent phases.
- Don't fabricate demo transcript text as actual YouTube content. Mark generated demo data as fixture data.

## Acceptance criteria (must demonstrate)
Adversarial and unauthorized access tests run; unsafe inputs rejected; no prompt-injection causes tool execution, prompt override, cross-tenant leakage or fabricated citation; report remaining risks and severity.

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
