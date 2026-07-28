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
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Worker

```bash
cd apps/worker
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m app.main
```

## Testing

```bash
# API tests
cd apps/api && pip install -e ".[dev]" && pytest -v

# Worker tests
cd apps/worker && pip install -e ".[dev]" && pytest -v

# TypeScript type checks
npm run typecheck

# Formatting
npx prettier --check .
```

## Docker Compose Profiles

| Profile | Services     | Command                                                                                         |
| ------- | ------------ | ----------------------------------------------------------------------------------------------- |
| default | All          | `docker compose -f infra/compose/docker-compose.yml up`                                         |
| dev     | + hot reload | `docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml up` |
