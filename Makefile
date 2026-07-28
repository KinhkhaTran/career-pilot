.PHONY: help setup venv build-packages dev dev-api dev-worker dev-dashboard test test-js test-python test-state-machine test-discovery discover lint lint-js lint-python typecheck migrate seed docker-up docker-down docker-logs docker-validate secret-scan check-no-submit-bypass ci clean

# Load local environment (DATABASE_URL, REDIS_URL, ...) so Python targets and the
# natively-run API/worker inherit them. Real shell env vars still take precedence.
ifneq (,$(wildcard .env))
include .env
export
endif

PYTHON_SERVICES = services/api services/worker
NPM_CMD = npm

# Services require Python >=3.12. The repo venv is created from this interpreter;
# override on the command line if yours is named differently (e.g. BOOTSTRAP_PYTHON=python3.12).
BOOTSTRAP_PYTHON ?= python3.13
VENV = .venv
VENV_BIN = $(VENV)/bin
PYTHON = $(VENV_BIN)/python
PIP = $(VENV_BIN)/pip

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

$(VENV): ## Create the Python virtualenv (from $(BOOTSTRAP_PYTHON))
	$(BOOTSTRAP_PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip

venv: $(VENV) ## Create the Python virtualenv if missing

setup: $(VENV) ## One-time local setup: install all deps and build shared TS packages
	$(NPM_CMD) install
	$(PIP) install -e "services/api[dev]" -e "services/worker[dev]"
	$(MAKE) build-packages
	@echo "==> Setup complete. Copy .env.example to .env and adjust values if you haven't already."

build-packages: ## Build shared TS packages (contracts, ui) — required before the dashboard can resolve them
	$(NPM_CMD) run build -w @career-pilot/contracts -w @career-pilot/ui

docker-up: ## Start PostgreSQL and Redis via Docker Compose (data stores only; run the API/worker natively)
	docker compose -f infra/docker-compose.yml up -d postgres redis

docker-down: ## Stop Docker Compose services
	docker compose -f infra/docker-compose.yml down

docker-logs: ## Tail Docker Compose logs
	docker compose -f infra/docker-compose.yml logs -f

migrate: ## Run database migrations (requires DB running). Runs from repo root; alembic paths are root-relative.
	$(VENV_BIN)/alembic -c db/alembic.ini upgrade head

seed: ## Load fake seed data (requires DB running and migrated)
	$(PYTHON) db/seeds/run_seeds.py

dev-api: ## Start the FastAPI service in development mode (reload)
	cd services/api && ../../$(VENV_BIN)/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker: ## Start the ARQ worker in development mode
	cd services/worker && ../../$(PYTHON) -m app.main

dev-dashboard: ## Start the Next.js dashboard in development mode
	cd apps/dashboard && $(NPM_CMD) run dev

dev: docker-up ## Start Docker deps and print where each service will run
	@echo "==> Docker deps up. Start services in separate terminals:"
	@echo "    make dev-api        # http://localhost:8000  (docs at /docs)"
	@echo "    make dev-dashboard  # http://localhost:3000"
	@echo "    make dev-worker"

test: test-js test-python ## Run all tests

test-js: ## Run JavaScript/TypeScript tests
	$(NPM_CMD) run test --workspaces --if-present

test-python: ## Run Python tests
	@for svc in $(PYTHON_SERVICES); do \
		echo "==> Testing $$svc"; \
		(cd $$svc && ../../$(PYTHON) -m pytest tests/ -v) || exit 1; \
	done

test-state-machine: ## Run state machine safety tests only
	cd services/api && ../../$(PYTHON) -m pytest tests/test_state_machine.py -v

test-discovery: ## Run discovery tests only (adapter + normalizer + API)
	cd services/worker && ../../$(PYTHON) -m pytest tests/test_normalizer.py tests/test_adapters.py tests/test_discovery.py -v
	cd services/api && ../../$(PYTHON) -m pytest tests/test_discovery.py -v

discover: ## Enqueue a discovery run (args: SOURCE=greenhouse COMPANY_ID=acme)
	@echo "==> Enqueuing discovery run: source=$(SOURCE) company_id=$(COMPANY_ID)"
	@cd services/worker && ../../$(PYTHON) -m app.cli discover "$(SOURCE)" "$(COMPANY_ID)"

lint: lint-js lint-python ## Run all linters

lint-js: ## Run ESLint and Prettier check
	$(NPM_CMD) run lint --workspaces --if-present
	npx prettier --check "**/*.{ts,tsx}" --ignore-path .gitignore

lint-python: ## Run ruff and mypy
	$(VENV_BIN)/ruff check services/ --config pyproject.toml
	$(VENV_BIN)/mypy services/ --config-file pyproject.toml

typecheck: ## Run TypeScript typechecks
	$(NPM_CMD) run typecheck --workspaces --if-present

docker-validate: ## Validate Docker Compose configuration
	docker compose -f infra/docker-compose.yml config --quiet

secret-scan: ## Scan for secrets in tracked files
	@echo "==> Scanning for secrets..."
	@git diff --cached --name-only | xargs grep -lE "(password|secret|token|api_key)\s*=\s*['\"][^'\"]{8,}" 2>/dev/null && echo "WARNING: Possible secrets found!" || echo "No secrets detected in staged files"
	@grep -rn "INITIAL_SUBMISSION_MODE=submit" . --include="*.py" --include="*.ts" --include="*.env" 2>/dev/null && echo "BLOCKED: submission mode not set to stop_before_submit" || echo "OK: submission mode check passed"

check-no-submit-bypass: ## Verify no submission bypass is present in source
	@echo "==> Checking for prohibited automation..."
	@grep -rn "captcha\|bypass_verification\|proxy_rotation\|inbox_code\|auto_submit" services/ --include="*.py" 2>/dev/null && echo "BLOCKED: prohibited automation found" || echo "OK: no prohibited automation"

ci: lint typecheck test docker-validate secret-scan check-no-submit-bypass ## Full CI check (mirrors GitHub Actions)

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name coverage -exec rm -rf {} + 2>/dev/null || true
	@echo "==> Cleaned build artifacts"
