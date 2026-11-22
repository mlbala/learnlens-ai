# LearnLens AI — developer commands (phase 01 vertical slice)
# Prefer fake AI providers. Do not run paid provider calls from make targets.

.DEFAULT_GOAL := help
SHELL := /bin/bash

UV ?= uv
PYTHON_VERSION ?= 3.12
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

.PHONY: help sync format lint typecheck test test-integration guardrails guardrails-harness eval eval-rag smoke smoke-e2e provider-smoke licenses dev migrate down clean check-tools docker-build docker-up docker-prod-config audit

help: ## Show available targets
	@echo "LearnLens AI — make targets"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Runtime: Python $(PYTHON_VERSION)+ via uv; Node >=20.19 for apps/web"
	@echo "Default AI providers: fake (see .env.example). No paid API calls from make."
	@echo "Data stores: Neon + Qdrant Cloud via env vars (no local DB volumes)."
	@echo "Deploy docs: infra/deploy/ (do not deploy without operator permission)."

check-tools: ## Verify local tooling (uv, python, node)
	@command -v $(UV) >/dev/null || (echo "blocker: uv not found — install https://docs.astral.sh/uv/"; exit 1)
	@$(UV) python find $(PYTHON_VERSION) >/dev/null || $(UV) python install $(PYTHON_VERSION)
	@command -v node >/dev/null || (echo "blocker: node not found (need >=20.19)"; exit 1)
	@node -e "const [maj,min]=process.versions.node.split('.').map(Number); if(maj<20||(maj===20&&min<19)){console.error('blocker: node >=20.19 required, got',process.versions.node); process.exit(1)}"
	@echo "tools ok: uv=$$($(UV) --version), python=$$($(UV) run --python $(PYTHON_VERSION) python -V), node=$$(node -v)"

sync: check-tools ## Install Python + Node workspace deps (offline-safe defaults)
	@$(UV) sync --python $(PYTHON_VERSION)
	@$(UV) sync --python $(PYTHON_VERSION) --project apps/api
	@npm install --ignore-scripts

format: sync ## Format Python with ruff
	@$(UV) run ruff format apps/api tests
	@$(UV) run --project apps/api ruff format apps/api

lint: sync ## Lint Python with ruff
	@$(UV) run ruff check apps/api tests
	@$(UV) run --project apps/api ruff check apps/api

typecheck: sync ## Typecheck API (compileall) + web (tsc)
	@$(UV) run --project apps/api python -m compileall -q apps/api/app
	@npm run typecheck --workspace=@learnlens/web
	@echo "typecheck: Python compileall ok; web tsc ok"

audit: sync ## Dependency vulnerability scan (pip-audit + npm audit; offline-friendly)
	@$(UV) run --project apps/api --with pip-audit pip-audit --skip-editable
	@npm audit --omit=dev --audit-level=high || true
	@echo "audit: reviewed (pip-audit strict; npm audit advisory — fix critical/high before release)"

test: sync ## Run offline unit tests (fake providers; mocked health probes)
	@$(UV) run --project apps/api pytest apps/api/tests tests -m "not integration"
	@npm run test --workspace=@learnlens/web
	@bash scripts/check_layout.sh

guardrails: sync ## AI/chat guardrails + security gate (fake providers only)
	@$(UV) run --project apps/api pytest \
		apps/api/tests/test_ai_guardrails.py \
		apps/api/tests/test_guardrail_framework.py \
		apps/api/tests/test_guardrails_harness.py \
		apps/api/tests/test_security_gate.py \
		apps/api/tests/test_grounded_qa.py \
		apps/api/tests/test_qa_evidence.py \
		apps/api/tests/test_tenant_isolation.py \
		-m "not integration" -q
	@$(MAKE) guardrails-harness
	@npm run test --workspace=@learnlens/web -- tests/xss-escape.test.tsx tests/citations.test.ts tests/evidence-citation.test.tsx
	@echo "guardrails: NeMo/HF-ready scanners + harness/regen loops + security tests ok"

guardrails-harness: sync ## Offline injection corpus + bounded regen-loop harness
	@$(UV) run --project apps/api python -m app.guardrails_harness \
		--out "$(ROOT)/artifacts/guardrails" --backend structured

test-integration: sync ## Hit Neon + Qdrant Cloud when credentials exist in env/.env
	@$(UV) run --project apps/api pytest apps/api/tests/test_health_integration.py -m integration

eval: sync ## Full offline eval suite — RAG + tutor + guardrails (fake providers)
	@$(UV) run --project apps/api python -m app.eval.cli --suite all --out "$(ROOT)/artifacts/eval"

eval-rag: sync ## RAG golden eval only (hard + regression gates)
	@$(UV) run --project apps/api python -m app.eval.cli --suite rag --out "$(ROOT)/artifacts/eval/rag"

smoke: ## Opt-in smoke — API live/ready only (no paid AI)
	@curl -fsS http://127.0.0.1:8000/health/live | head -c 400; echo
	@curl -fsS http://127.0.0.1:8000/health/ready | head -c 400; echo

smoke-e2e: sync ## Offline e2e smoke (fixture video/playlist/adversarial; fake providers)
	@$(UV) run --project apps/api pytest apps/api/tests/test_e2e_smoke.py -q

provider-smoke: ## Opt-in live provider smoke — REFUSES unless ALLOW_PAID_SMOKE=1
	@if [ "$${ALLOW_PAID_SMOKE:-}" != "1" ]; then \
	  echo "provider-smoke: blocked (set ALLOW_PAID_SMOKE=1 explicitly; incurs cost)"; \
	  exit 2; \
	fi
	@echo "provider-smoke: not automated in phase 16 — run a single manual live call with operator keys"

licenses: sync ## Refresh offline dependency license inventory
	@$(UV) run --project apps/api python scripts/license_inventory.py

dev: ## Run API (uvicorn) — set Neon/Qdrant in .env first
	@$(UV) run --project apps/api uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

migrate: sync ## Apply Alembic migrations to Neon (uses DATABASE_URL_UNPOOLED or DATABASE_URL)
	@cd apps/api && $(UV) run alembic upgrade head

migrate-down: sync ## Downgrade one Alembic revision (Neon)
	@cd apps/api && $(UV) run alembic downgrade -1

down: ## Stop local compose services
	@docker compose -f compose.yaml --profile app --profile worker --profile redis down

docker-build: ## Build api + web images (worker shares api image; no paid APIs)
	@docker compose -f compose.yaml --profile app build
	@docker compose -f compose.yaml --profile worker build

docker-up: ## Run api + web containers (requires Neon/Qdrant env)
	@docker compose -f compose.yaml --profile app up --build

docker-prod-config: ## Validate compose.prod.yaml (requires env secrets; does not deploy)
	@docker compose -f compose.prod.yaml config >/dev/null
	@echo "compose.prod.yaml: config ok (secrets must be exported by operator)"

clean: ## Remove local caches (never deletes Neon/Qdrant cloud data)
	@rm -rf .venv apps/api/.venv .pytest_cache apps/api/.pytest_cache .ruff_cache apps/api/.ruff_cache
	@rm -rf node_modules apps/web/node_modules packages/contracts/node_modules
	@rm -rf apps/web/.next
	@find . -type d -name '__pycache__' -not -path './.git/*' -exec rm -rf {} + 2>/dev/null || true
	@echo "clean: local caches removed (cloud data untouched)"
