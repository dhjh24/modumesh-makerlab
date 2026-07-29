# ModuMesh MakerLab Architecture

## Overview

ModuMesh MakerLab is a self-hosted 3D generator platform built as a
monorepo with three application services and four shared packages.

## Services

### Web (Next.js)

- SSR React frontend
- `/api/health` endpoint
- Three.js / R3F model viewer (Phase 4)
- REST client to API service

### API (FastAPI)

- RESTful API for projects, jobs, and plugins
- `/health`, `/health/ready`, `/health/live` endpoints
- PostgreSQL for persistent state
- Redis for job queue
- MinIO for model file storage
- OpenAPI contract via FastAPI auto-docs

### Worker (Python)

- Polls Redis for queued generation jobs
- Executes plugins with resource limits
- Timeout, memory, network isolation per job
- Writes results to MinIO

## Data Flow

```
User → Web → API → Redis Queue → Worker → Plugin → MinIO → API → Web
```

## Key Rules

1. **No CAD generation in web requests** — always queued via Redis.
2. **Plugins are untrusted** — non-root, timeouts, memory caps, no network.
3. **Immutable records** — plugin version, input, output, validation, checksums.
4. **No shop integration until Phase 7 exit gate passes.**
5. **Strict job state machine** — only allowlisted transitions; retries create new attempts.

## Phase 2 — Projects & Job Engine

Durable projects and generation jobs with Redis-backed queue processing.

### Job state machine

```
created → queued → running → validating → uploading → completed
              ↘──────── cancel from any active state ────────→ cancelled
                         fail from running|validating|uploading → failed
```

### Queue behavior

- API enqueues job IDs on Redis list `modumesh:jobs:queue` (LPUSH).
- Worker consumers BRPOP jobs, claim with `SELECT … FOR UPDATE`, then process.
- Cooperative cancel via DB `cancel_requested` + Redis `modumesh:jobs:cancel:{id}`.
- Worker leases (`lease_expires_at`) renewed on heartbeat; reaper fails abandoned jobs.
- Sample job (`job_type=sample`) writes a small JSON artifact to MinIO with SHA-256.

## Technology Stack

| Layer      | Technology         |
| ---------- | ------------------ |
| Frontend   | Next.js + React    |
| Backend    | FastAPI            |
| Worker     | Python             |
| Database   | PostgreSQL 16      |
| Queue      | Redis 7            |
| Storage    | MinIO              |
| Container  | Docker Compose     |
| CAD Engine | CadQuery (Phase 5) |
| 3D Viewer  | Three.js / R3F     |
| Schema     | JSON Schema        |
