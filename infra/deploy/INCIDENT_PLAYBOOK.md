# Incident playbook (MVP)

Correlate with `X-Request-ID` / `trace_id`. Never paste raw transcripts, session cookies, or API keys into tickets or logs.

## Severity

| Level | Example | First response |
| --- | --- | --- |
| SEV1 | Cross-tenant data exposure; auth bypass | Disable public ingress; rotate `SESSION_SECRET` and provider keys; preserve audit_events |
| SEV2 | Neon or Qdrant outage; all readiness failing | Fail closed on writes; communicate degraded mode; check cloud status pages |
| SEV3 | Single provider 429/timeout; worker backlog | Open circuit cool-down; keep fake fallback for non-prod; scale worker concurrency carefully |
| SEV4 | UI-only / fixture demo issues | Track in backlog; no emergency change |

## Common incidents

### `/health/ready` degraded

1. Inspect `checks.neon` / `checks.qdrant` / `checks.redis` (no secrets in payload).
2. Confirm free-tier suspend (Qdrant idle) or Neon scale-to-zero wake.
3. Do not flip to paid providers automatically.

### Auth / CSRF failures spike

1. Verify `CORS_ORIGINS` exact match and `COOKIE_SECURE` vs HTTPS.
2. Confirm reverse proxy forwards cookies without stripping `SameSite`.
3. Check rate-limit responses (`429`) vs true `CSRF_FAILED`.

### Prompt-injection / hostile transcript

1. Treat as source data; confirm no outbound fetch to URLs inside captions.
2. Run offline security corpus: `fixtures/security/injection_corpus.jsonl`.
3. If a response leaked secrets, rotate keys and review PrivacyPolicy redaction.

### Job stuck / dead letter

1. See `infra/observability/RUNBOOK.md` — recover expired leases; do not unbounded retry.
2. Confirm idempotency keys / content hashes before re-queue.

### Suspected secret in git or image

1. Rotate immediately; purge from history only with explicit operator approval.
2. Confirm `.dockerignore` excludes `.env`; CI never prints env values.

## Communications

- Internal: request IDs, impact window, systems touched.
- External: no claim of “transcript analyzed from public URL only”; honest coverage / partial playlist language.

## Post-incident

Update this playbook if a new failure mode appears. Optional phases must not be hotfixed into production without a scoped change request.
