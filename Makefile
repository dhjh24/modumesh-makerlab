# ─── ModuMesh MakerLab Makefile ────────────────────────────────────────
# Development commands for the full stack.
# Usage: make <target>

DOCKER_COMPOSE = docker compose -f infra/compose/docker-compose.yml
DOCKER_COMPOSE_DEV = docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml

.PHONY: start stop logs reset migrate api-shell db-shell ps lint test test-api test-worker smoke ci-build help

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
	make test-api
	make test-worker

test-api: ## Run API unit tests
	cd apps/api && pip install -q -e ".[dev]" && python -m pytest -v

test-worker: ## Run worker unit tests
	cd apps/worker && pip install -q -e ".[dev]" && python -m pytest -v

smoke:    ## Run integration smoke tests against running stack
	$(DOCKER_COMPOSE) exec api python -m pytest tests/test_integration.py tests/test_phase2_integration.py -v -x

# ── Linting ───────────────────────────────────────────────────────────

lint:     ## Run all linters
	npx prettier --check .
	cd apps/api && pip install -q -e ".[dev]" && python -m flake8 app/ 2>/dev/null || true
	cd apps/worker && pip install -q -e ".[dev]" && python -m flake8 app/ 2>/dev/null || true

format:   ## Auto-format code
	npx prettier --write .

# ── CI helper ─────────────────────────────────────────────────────────

ci-build: ## Build containers (used by CI)
	$(DOCKER_COMPOSE) build

# ── Help ──────────────────────────────────────────────────────────────

help:     ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
