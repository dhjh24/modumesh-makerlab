# ModuMesh MakerLab Architecture

## Overview

ModuMesh MakerLab is a self-hosted 3D generator platform built as a
monorepo with three application services and four shared packages.

## Services

### Web (Next.js)

- SSR React frontend (Pages Router)
- Home dashboard, generator catalog, project editor
- Schema-driven parameter forms from plugin `input_schema`
- Lazy-loaded Three.js / R3F viewer (`@modumesh/viewer`) for STL/GLB
- REST client to API (`NEXT_PUBLIC_API_URL` or same-origin `/api/v1` rewrites)
- `/api/health` endpoint (web process only)

### API (FastAPI)

- RESTful API for projects, jobs, and plugins
- `/health`, `/health/ready`, `/health/live` endpoints
- PostgreSQL for persistent state
- Redis for job queue
- MinIO for model file storage
- OpenAPI contract via FastAPI auto-docs

### Worker (Python)

- Polls Redis for queued generation jobs
- Executes plugins with resource limits via the plugin SDK runner
- Timeout, memory, network isolation per job
- Writes results to MinIO

## Plugins

- Discovered from `API_PLUGIN_DIR` / `WORKER_PLUGIN_DIR` (default `/plugins`)
- Manifest contract: `docs/plugins.md` and ADR-0003
- Enable/disable state persisted in PostgreSQL `plugin_registry`
- Example non-CAD plugins: `plugins/fixture-echo`, `plugins/fixture-mesh` (STL/GLB fixtures)
- Nameplate CadQuery plugin lands in Phase 5

## Data Flow

```
User → Web → API → Redis Queue → Worker → Plugin → MinIO → API → Web
```

## Key Rules

1. **No CAD generation in web requests** — always queued via Redis.
2. **Plugins are untrusted** — non-root, timeouts, memory caps, no network by default.
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

## Phase 4 — Viewer & Schema-Driven Editor

User-facing catalog and editor without hard-coded generator forms:

1. **Home** — recent projects, create project, catalog preview, job activity.
2. **Catalog** — `GET /api/v1/plugins` metadata + schema preview forms.
3. **Editor** — parameter panel (schema form), lazy 3D viewer, project/version/file panels, job status polling (`queued` → `completed`/`failed`/`cancelled`).
4. **Viewer** — STL/GLB, orbit controls, wireframe, build plate, bounding box, dimensions; reduced-motion aware.
5. **Fixtures** — `public/fixtures/sample-cube.{stl,glb}` and `plugins/fixture-mesh` for job-produced meshes.

Phase 5 adds the real CadQuery Nameplate generator — do not hard-code that form here.
