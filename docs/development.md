# Development Guide

## Prerequisites

- **Node.js** >= 22
- **npm** >= 10
- **Python** >= 3.11
- **Docker** >= 29
- **Docker Compose** (v2)

## One-Command Start

```bash
docker compose -f infra/compose/docker-compose.yml up -d
```

This starts PostgreSQL, Redis, MinIO, the API, the worker, and the web app.

## Local Development Without Docker

### Frontend

```bash
npm install
cd apps/web
npm run dev    # http://localhost:3000
```

### API

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../../packages/plugin-sdk-py
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Worker

```bash
cd apps/worker
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../../packages/plugin-sdk-py
pip install -e ".[dev]"
python -m app.main
```

## Testing

```bash
# Plugin contract CLI (authors + CI)
pip install -e packages/plugin-sdk-py
modumesh-plugin-check check plugins/fixture-echo \
  --input plugins/fixture-echo/fixtures/valid-input.json
modumesh-plugin-check check plugins/fixture-mesh \
  --input plugins/fixture-mesh/fixtures/valid-input.json

# API tests (install SDK first)
pip install -e packages/plugin-sdk-py
cd apps/api && pip install -e ".[dev]" && pytest -v

# Worker tests
pip install -e packages/plugin-sdk-py
cd apps/worker && pip install -e ".[dev]" && pytest -v

# TypeScript type checks
npm run typecheck

# Formatting
npx prettier --check .

# Integration smoke (stack must be running)
make smoke

# Web e2e + a11y (stack must be running on :3000 / :8000)
cd apps/web && npx playwright install chromium
npm run test:e2e --workspace=@modumesh/web
```

## CI

Continuous integration runs on **GitHub Actions** (`.github/workflows/ci.yml`)
on the dedicated self-hosted runner `ci` (`10.10.10.235`) with labels
`self-hosted`, `linux`, `x64`, `ci`, `modumesh-makerlab`:

- Prettier lint
- TypeScript typecheck
- Plugin contract tests (`modumesh-plugin-check` + SDK unit tests)
- API and worker unit tests
- Docker Compose image build
- Integration smoke against Postgres, Redis, MinIO (Phase 2 + Phase 3 plugin flows)

Jobs must not use GitHub-hosted runners (`ubuntu-latest`) or a bare
`self-hosted` label.

## Docker Compose Profiles

| Profile | Services     | Command                                                                                         |
| ------- | ------------ | ----------------------------------------------------------------------------------------------- |
| default | All          | `docker compose -f infra/compose/docker-compose.yml up`                                         |
| dev     | + hot reload | `docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml up` |
