# LearnLens AI — developer commands (phase 00 scaffolding)
# Prefer fake AI providers. Do not run paid provider calls from make targets.

.DEFAULT_GOAL := help
SHELL := /bin/bash

UV ?= uv
PYTHON_VERSION ?= 3.12
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

.PHONY: help sync format lint typecheck test test-integration smoke dev migrate down clean check-tools docker-build docker-up

help: ## Show available targets
	@echo "LearnLens AI — make targets"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'
	@echo ""
	@echo "Runtime: Python $(PYTHON_VERSION)+ via uv; Node >=20.19 for apps/web"
	@echo "Default AI providers: fake (see .env.example). No paid API calls from make."

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

typecheck: sync ## Typecheck API with Python (py_compile); web deferred
	@$(UV) run --project apps/api python -m compileall -q apps/api/app
	@npm run typecheck
	@echo "typecheck: Python compileall ok; web/contracts deferred stubs ok"

test: sync ## Run offline unit tests (fake providers; no network)
	@$(UV) run --project apps/api pytest apps/api/tests tests
	@bash scripts/check_layout.sh

test-integration: ## Integration tests (not wired in phase 00)
	@echo "test-integration: deferred until phase 01+ (Neon/Qdrant/Redis)"

smoke: ## Opt-in smoke (not wired; must not call paid APIs in phase 00)
	@echo "smoke: deferred until phase 01; keep AI_*_PROVIDER=fake"

dev: ## Local stack (not wired in phase 00)
	@echo "dev: deferred until phase 01 vertical slice"

migrate: ## DB migrations (not wired in phase 00)
	@echo "migrate: deferred until phase 02"

down: ## Stop local compose services
	@docker compose -f compose.yaml --profile app --profile redis down

docker-build: ## Build api + web images (no paid APIs)
	@docker compose -f compose.yaml --profile app build

docker-up: ## Run api + web scaffold containers
	@docker compose -f compose.yaml --profile app up --build

clean: ## Remove local caches (never deletes Neon/Qdrant cloud data)
	@rm -rf .venv apps/api/.venv .pytest_cache apps/api/.pytest_cache .ruff_cache apps/api/.ruff_cache
	@rm -rf node_modules apps/web/node_modules packages/contracts/node_modules
	@find . -type d -name '__pycache__' -not -path './.git/*' -exec rm -rf {} + 2>/dev/null || true
	@echo "clean: local caches removed (cloud data untouched)"
