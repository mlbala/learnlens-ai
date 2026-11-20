# LearnLens observability & cost runbook (phase 15)

## Principles

- Never log raw transcript text, API keys, or model chain-of-thought.
- Correlate with `X-Request-ID` / `trace_id` / W3C `traceparent` across Next.js → FastAPI → Celery.
- Costs are **estimates** (`estimate_version=v0-placeholder-not-live-rates`). Do not bill from them.
- Jobs use unique idempotency / request-hash keys for exactly-once *effects*, not exactly-once *execution*.

## Health

```bash
curl -sS http://127.0.0.1:8000/health/live
curl -sS http://127.0.0.1:8000/health/ready
```

Ready requires Neon + Qdrant. Redis is required only when `CELERY_TASK_ALWAYS_EAGER=false`.

## Usage & quotas

```bash
# Authenticated session cookies required
curl -sS -b cookies.txt 'http://127.0.0.1:8000/api/v1/usage'
```

On `USAGE_QUOTA_EXCEEDED` / `WORKSPACE_*_QUOTA_EXCEEDED` (429): raise caps via env
(`USAGE_WORKSPACE_*`) or wait for the period (`YYYY-MM`) to roll.

## Provider outage / circuit open

1. Confirm error code `PROVIDER_TEMPORARILY_UNAVAILABLE` or `PROVIDER_CIRCUIT_OPEN`.
2. Check circuit cooldown (`CIRCUIT_RECOVERY_TIMEOUT_SECONDS`).
3. Do **not** silently switch paid providers.
4. Failed jobs after max attempts land in dead-letter semantics (`JOB_DEAD_LETTER` or original code) with `actionable=true` in the taxonomy.

## Stuck jobs

```python
# From an API shell / operator script (fake providers only in local)
from app.core.observability.job_recovery import recover_expired_leases
recovered = await recover_expired_leases(session)
```

Re-queued jobs must remain idempotent (content hash / idempotency key).

## Sample dashboard

See `infra/observability/sample-dashboard.json` for panel ideas. Wire to your log sink later (phase 16 CI/deploy may add exporters).

## Manual verification (offline)

```bash
make lint && make typecheck && make test
# Then:
cd apps/api && uv run pytest tests/test_observability_cost.py -q
```
