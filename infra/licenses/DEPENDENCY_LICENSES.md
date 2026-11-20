# Dependency license inventory

**Not legal advice.** Operators should re-verify licenses before redistribution.

Machine-readable snapshot: [`dependency-licenses.json`](./dependency-licenses.json) (offline generation; no paid APIs).

Regenerate after dependency bumps:

```bash
uv run --project apps/api python scripts/license_inventory.py
```

## Python (API / worker — direct runtime)

See JSON for pinned versions discovered in the local environment. Primary packages include FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic, asyncpg, Argon2, Qdrant client, OpenAI / Google GenAI SDKs, Celery, Redis, python-multipart.

## JavaScript (web — highlights)

| Package | Typical license | Notes |
| --- | --- | --- |
| next | MIT | App Router frontend |
| react / react-dom | MIT | UI runtime |
| typescript | Apache-2.0 | Build-time |
| vitest | MIT | Offline unit tests |
| tailwindcss | MIT | Styling |

Run `npm ls` / license scanners in CI or release reviews for the full transitive tree. Treat `npm audit` / `pip-audit` findings as release gates (warnings today must be triaged before public launch).
