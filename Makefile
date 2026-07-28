.PHONY: help setup dev test lint typecheck migrate seed discover docker-up docker-down docker-logs clean

PYTHON_SERVICES = services/api services/worker
NPM_CMD = npm

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## One-time local setup: install deps for all workspaces
	$(NPM_CMD) install
	@for svc in $(PYTHON_SERVICES); do \
		echo "==> Installing $$svc"; \
		cd $$svc && pip install -e ".[dev]" && cd ../..; \
	done
	@echo "==> Setup complete. Copy .env.example to .env and adjust values."

docker-up: ## Start PostgreSQL, Redis, and mock-ats via Docker Compose
	docker compose -f infra/docker-compose.yml up -d

docker-down: ## Stop Docker Compose services
	docker compose -f infra/docker-compose.yml down

docker-logs: ## Tail Docker Compose logs
	docker compose -f infra/docker-compose.yml logs -f

migrate: ## Run database migrations (requires DB running)
	cd db && alembic upgrade head

seed: ## Load fake seed data (requires DB running and migrated)
	python db/seeds/run_seeds.py

dev-api: ## Start the FastAPI service in development mode
	cd services/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker: ## Start the ARQ worker in development mode
	cd services/worker && python -m app.main

dev-dashboard: ## Start the Next.js dashboard in development mode
	cd apps/dashboard && npm run dev

dev: docker-up ## Start all services (Docker deps + API + worker + dashboard)
	@echo "==> Starting all services..."
	@echo "Dashboard: http://localhost:3000"
	@echo "API:       http://localhost:8000"
	@echo "API docs:  http://localhost:8000/docs"

test: test-js test-python ## Run all tests

test-js: ## Run JavaScript/TypeScript tests
	$(NPM_CMD) run test --workspaces --if-present

test-python: ## Run Python tests
	@for svc in $(PYTHON_SERVICES); do \
		echo "==> Testing $$svc"; \
		cd $$svc && python -m pytest tests/ -v && cd ../..; \
	done

test-state-machine: ## Run state machine safety tests only
	cd services/api && python -m pytest tests/test_state_machine.py -v

test-discovery: ## Run discovery tests only (adapter + normalizer + API)
	cd services/worker && python -m pytest tests/test_normalizer.py tests/test_adapters.py tests/test_discovery.py -v
	cd services/api && python -m pytest tests/test_discovery.py -v

discover: ## Enqueue a discovery run (args: SOURCE=greenhouse COMPANY_ID=acme)
	@echo "==> Enqueuing discovery run: source=$(SOURCE) company_id=$(COMPANY_ID)"
	@cd services/worker && python -c "\
import asyncio; \
from arq import create_pool; \
from arq.connections import RedisSettings; \
async def main(): \
    redis = await create_pool(RedisSettings()); \
    await redis.enqueue_job('discover_jobs_task', source='$(SOURCE)', company_id='$(COMPANY_ID)'); \
    print('Enqueued discover_jobs_task for $(SOURCE):$(COMPANY_ID)'); \
asyncio.run(main())"

lint: lint-js lint-python ## Run all linters

lint-js: ## Run ESLint and Prettier check
	$(NPM_CMD) run lint --workspaces --if-present
	npx prettier --check "**/*.{ts,tsx}" --ignore-path .gitignore

lint-python: ## Run ruff and mypy
	ruff check services/ --config pyproject.toml
	mypy services/ --config-file pyproject.toml

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
