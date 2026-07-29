# ─── ModuMesh MakerLab Makefile ────────────────────────────────────────
# Development commands for the full stack.
# Usage: make <target>

DOCKER_COMPOSE = docker compose -f infra/compose/docker-compose.yml
DOCKER_COMPOSE_DEV = docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml

.PHONY: start stop logs reset migrate api-shell db-shell ps lint test test-api test-worker test-plugin-sdk test-nameplate smoke test-e2e ci-build help

# ── Stack lifecycle ───────────────────────────────────────────────────

start:    ## Start the full stack in background
	$(DOCKER_COMPOSE) up -d

start-dev: ## Start with hot-reload for development
	$(DOCKER_COMPOSE_DEV) up -d

stop:     ## Stop the stack
	$(DOCKER_COMPOSE) down

logs:     ## Tail logs from all services
	$(DOCKER_COMPOSE) logs -f

ps:       ## Show running services
	$(DOCKER_COMPOSE) ps

reset:    ## Stop and remove volumes (WARNING: destroys data)
	$(DOCKER_COMPOSE) down -v

build:    ## Build all containers
	$(DOCKER_COMPOSE) build

# ── Database ──────────────────────────────────────────────────────────

migrate:  ## Run Alembic migrations
	$(DOCKER_COMPOSE) exec api alembic -c /app/alembic.ini upgrade head

migrate-check: ## Show migration status
	$(DOCKER_COMPOSE) exec api alembic -c /app/alembic.ini current

migrate-history: ## Show migration history
	$(DOCKER_COMPOSE) exec api alembic -c /app/alembic.ini history

db-shell: ## Open psql shell
	$(DOCKER_COMPOSE) exec postgres psql -U modumesh modumesh

# ── Testing ───────────────────────────────────────────────────────────

test:     ## Run all unit tests
	make test-plugin-sdk
	make test-nameplate
	make test-api
	make test-worker

test-plugin-sdk: ## Run plugin SDK + contract CLI checks
	pip install -q -e packages/plugin-sdk-py
	cd packages/plugin-sdk-py && python -m pytest -v
	modumesh-plugin-check check plugins/fixture-echo --input plugins/fixture-echo/fixtures/valid-input.json
	modumesh-plugin-check check plugins/fixture-mesh --input plugins/fixture-mesh/fixtures/valid-input.json
	modumesh-plugin-check check plugins/nameplate --input plugins/nameplate/fixtures/valid-input.json --no-run

test-nameplate: ## Run Nameplate unit + geometry regression tests
	pip install -q -e packages/plugin-sdk-py
	pip install -q "cadquery>=2.4.0,<3" "trimesh>=4.0.0" "pillow>=10.0.0" "numpy>=1.26.0" pytest
	cd plugins/nameplate && PYTHONPATH=src python -m pytest -v

test-api: ## Run API unit tests
	pip install -q -e packages/plugin-sdk-py
	cd apps/api && pip install -q -e ".[dev]" && python -m pytest tests/test_health.py tests/test_state_machine.py tests/test_plugins_unit.py -v

test-worker: ## Run worker unit tests
	pip install -q -e packages/plugin-sdk-py
	cd apps/worker && pip install -q -e ".[dev]" && python -m pytest -v

smoke:    ## Run integration smoke tests against running stack
	$(DOCKER_COMPOSE) exec api python -m pytest tests/test_integration.py tests/test_phase2_integration.py tests/test_phase3_integration.py tests/test_phase5_integration.py -v -x

test-e2e: ## Run Playwright e2e + a11y (web + API must be up)
	cd apps/web && npx playwright test --project=chromium

# ── Linting ───────────────────────────────────────────────────────────

lint:     ## Run all linters
	npx prettier --check .
	cd apps/api && pip install -q -e ".[dev]" && python -m flake8 app/ 2>/dev/null || true
	cd apps/worker && pip install -q -e ".[dev]" && python -m flake8 app/ 2>/dev/null || true

format:   ## Auto-format code
	npx prettier --write .

# ── CI helper ─────────────────────────────────────────────────────────

ci-build: ## Build containers (used by CircleCI)
	$(DOCKER_COMPOSE) build

# ── Help ──────────────────────────────────────────────────────────────

help:     ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
