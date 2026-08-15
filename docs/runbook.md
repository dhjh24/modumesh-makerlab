# ModuMesh MakerLab — Operator Runbook

This document describes procedures for common operational tasks,
incident response, and recovery.

## Service overview

The MakerLab runs as a set of Docker containers on a single host:

| Service  | Port                 | Description                                     |
| -------- | -------------------- | ----------------------------------------------- |
| API      | 8002 (host) → 8000   | FastAPI backend                                 |
| Web      | 3002 (host) → 3000   | Next.js frontend                                |
| Worker   | —                    | Celery-like job worker (Redis queue)            |
| Postgres | 5432 (internal)      | Job/plugin/file metadata — no host port         |
| Redis    | 6379 (internal)      | Job queue and cache — no host port              |
| MinIO    | 9000/9001 (internal) | Object storage (generated files) — no host port |

## Health checks

```bash
# Get overall health
curl http://localhost:8002/api/v1/health
curl http://localhost:8002/api/v1/health/full

# Check container status
docker compose -f infra/compose/docker-compose.yml ps
```

## Authentication

Per-user routes (projects, jobs, files, shop, compare) require a bearer token;
anonymous calls get 401.

```bash
# Register (returns access_token + user)
curl -X POST http://localhost:8002/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"change-me-8chars","display_name":"You"}'

# Login
curl -X POST http://localhost:8002/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"change-me-8chars"}'

# Use the token on per-user routes
export TOKEN=<access_token>
curl http://localhost:8002/api/v1/projects -H "Authorization: Bearer $TOKEN"

# Logout revokes the presented token
curl -X POST http://localhost:8002/api/v1/auth/logout -H "Authorization: Bearer $TOKEN"
```

- Tokens expire after `API_TOKEN_TTL_HOURS` (default 24) and are stored
  hashed (SHA-256) — a DB leak does not expose usable tokens.
- Register/login are rate-limited to 5/min per IP; authenticated requests are
  rate-limited per user (job submission cap is per owner, not per IP).
- Cross-user access returns 404 (not 403) so resource existence is not leaked.
- Admin endpoints use `ADMIN_API_KEY` (see Plugin management) — user auth does
  not grant admin rights; health/catalog/plugin-list stay public.

## Restarting services

```bash
# Restart a single service after a config or code change
docker compose -f infra/compose/docker-compose.yml up -d --no-deps api

# Rebuild and restart all services
docker compose -f infra/compose/docker-compose.yml up -d --build
```

## Viewing logs

```bash
docker logs compose-api-1 --tail 50
docker logs compose-worker-1 --tail 50

# Follow logs
docker logs compose-api-1 -f
```

## Plugin management

```bash
# Admin-only: set ADMIN_API_KEY in your shell first (see .env.example)
export ADMIN_API_KEY=your_admin_key

# Re-scan plugin directories
curl -s -X POST -H "Authorization: Bearer $ADMIN_API_KEY" http://localhost:8002/api/v1/plugins/resync

# Enable/disable a plugin
curl -s -X POST -H "Authorization: Bearer $ADMIN_API_KEY" http://localhost:8002/api/v1/plugins/nameplate/enable
curl -s -X POST -H "Authorization: Bearer $ADMIN_API_KEY" http://localhost:8002/api/v1/plugins/nameplate/disable
```

## Job management

```bash
# List recent jobs
curl -s "http://localhost:8002/api/v1/projects/<project-id>/jobs?limit=10"

# Check a specific job
curl -s "http://localhost:8002/api/v1/jobs/<job-id>"

# Cancel a running job
curl -s -X POST "http://localhost:8002/api/v1/jobs/<job-id>/cancel"
```

## Storage

```bash
# List files in a project
curl -s "http://localhost:8002/api/v1/projects/<project-id>/files"

# Download a file
curl -s "http://localhost:8002/api/v1/files/<file-id>/download"
```

## Backup and recovery

The most critical data is Postgres (metadata) and MinIO (generated files).
Automated backups are provided by `scripts/backup.sh` (GM-12 D2).

### How automated backups work

`scripts/backup.sh` runs on a schedule (daily recommended) and:

1. `pg_dump -Fc` of Postgres → a timestamped `.dump` file in `BACKUP_DIR`
   (default `/var/backups/modumesh`).
2. Uploads the dump to the MinIO `modumesh-backups/postgres/` prefix.
3. `mc mirror --overwrite` of the `modumesh-models` bucket →
   `modumesh-backups/models` (incremental — only changed objects).
4. Writes a manifest + `SHA256SUMS` alongside (local and remote `manifests/`).
5. Prunes artifacts older than `BACKUP_RETENTION_DAYS` (default 14), local and
   remote.

The script **fails loudly**: any failed step exits non-zero with a `FATAL`
message, and it refuses to run without credentials (`PGPASSWORD`,
`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`). It is idempotent and safe to run
from cron; `PRUNE_ONLY=1` runs just the retention prune.

Environment (also mirrored in `infra/compose/docker-compose.yml` `backup`
service and `.env.example`):

```bash
export PGHOST=localhost PGPORT=5432 PGUSER=modumesh PGDATABASE=modumesh
export PGPASSWORD=<pg password>
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=<minio access key> MINIO_SECRET_KEY=<minio secret key>
export BACKUP_DIR=/var/backups/modumesh
export BACKUP_RETENTION_DAYS=14
```

Where backups live:

- Local staging: `BACKUP_DIR` (default `/var/backups/modumesh`) on the host.
- Remote copy: MinIO bucket `modumesh-backups` (`postgres/`, `models/`,
  `manifests/`).
- **Never commit backup artifacts to git.** The `backups/` directory is
  git-ignored and untracked — dumps and MinIO objects are frequently large,
  contain secrets (DB credentials, tokens, user data), and bloating the
  repository history is unrecoverable. Store backups **outside the repo** and
  keep only scripts/config in the repo.

Scheduling (host cron, recommended — the compose `backup` service image lacks
`pg_dump`/`mc` unless extended):

```cron
# daily at 02:30 host time; a wrapper can alert on non-zero exit
30 2 * * * cd /home/dirk/modumesh-makerlab && BACKUP_TARGET=modumesh bash scripts/backup.sh >> /var/log/modumesh-backup.log 2>&1
```

### Restore procedure

> A CI `restore-drill` job (weekly schedule + `workflow_dispatch`) asserts the
> backup scripts exist, are executable, syntax-clean and fail-loud, dry-runs
> the retention prune, and prints this exact procedure. Upgrade it to a full
> containerized drill once the backup image carries `postgresql-client` + `mc`.

1. Identify the latest backup:

```bash
mc alias set modumesh http://localhost:9000 <access-key> <secret-key>
mc ls --recursive modumesh/modumesh-backups/postgres/
```

2. Restore Postgres onto a fresh stack with an EMPTY `pgdata` volume:

```bash
docker compose -f infra/compose/docker-compose.yml down -v   # WIPES volumes — only on a fresh/empty target
docker compose -f infra/compose/docker-compose.yml up -d postgres
LATEST=$(mc ls --recursive modumesh/modumesh-backups/postgres/ | tail -1 | awk '{print $NF}')
mc cat "modumesh/modumesh-backups/postgres/${LATEST}" \
  | docker compose -f infra/compose/docker-compose.yml exec -T postgres \
      pg_restore -U modumesh -d modumesh --clean --if-exists
```

3. Restore MinIO models (overwrite mirror):

```bash
docker compose -f infra/compose/docker-compose.yml up -d minio
mc mirror --overwrite modumesh/modumesh-backups/models modumesh/modumesh-models
```

4. Start the rest of the stack and verify:

```bash
docker compose -f infra/compose/docker-compose.yml up -d
curl -fsS http://localhost:8002/api/v1/health/ready
curl -fsS http://localhost:8002/api/v1/health/full
# Spot-check a known project's file download:
curl -fsS -H "Authorization: Bearer <token>" \
  http://localhost:8002/api/v1/files/<file-id>/download -o model.stl
```

### Manual Postgres dump (fallback)

```bash
docker exec compose-db-1 pg_dump -U modumesh modumesh > makerlab-backup-$(date +%Y%m%d).sql
```

## Deployment

### Migrations are an explicit deploy step (GM-12 D1.6)

The API no longer auto-runs `alembic upgrade head` at boot (opt in with
`API_RUN_MIGRATIONS=1` for single-instance deployments). Run migrations
explicitly BEFORE starting the new API version:

```bash
docker compose -f infra/compose/docker-compose.yml build api
docker compose -f infra/compose/docker-compose.yml up -d postgres redis minio
docker compose -f infra/compose/docker-compose.yml \
  exec -T api alembic -c /app/alembic.ini upgrade head
docker compose -f infra/compose/docker-compose.yml up -d api worker web
```

On migration failure the API will start but report degraded readiness — check
`docker logs compose-api-1 | grep -i migration` first.

### Non-development environments are fail-closed (GM-12 D1.2/D1.4)

With `API_ENV` anything other than `development` (compose default
`API_ENV=development`):

- The API refuses to boot while `POSTGRES_PASSWORD`/`MINIO_SECRET_KEY` are the
  documented defaults or `REDIS_PASSWORD` is empty (names the offenders in the
  error).
- `/docs`, `/redoc` and `/openapi.json` return 404 (interactive docs disabled).

Production must set `API_ENV=production`, `REDIS_PASSWORD` (compose `redis`
runs `redis-server --requirepass ${REDIS_PASSWORD:-}` — GM-12 D1.1), and
strong datastore secrets.

### CI runner (GM-12 D3.5)

All workflows in `.github/workflows/ci.yml` run on a dedicated self-hosted
runner, never GitHub-hosted. The runner must be registered on **ci-1
(100.109.168.32)** — the old ci host (10.10.10.235) is offline — with labels
`self-hosted, linux, x64, ci, modumesh-makerlab` (the exact `runs-on` label
set every job uses). One-time ops step, no code:

```bash
# On ci-1, as the runner service account:
# 1. Get a registration token (owner/admin of the repo):
TOKEN="$(gh api -X POST repos/dhjh24/modumesh-makerlab/actions/runners/registration-token --jq .token)"
# 2. Register (use the actions-runner tarball from GitHub releases):
./config.sh --url https://github.com/dhjh24/modumesh-makerlab \
  --token "$TOKEN" --labels self-hosted,linux,x64,ci,modumesh-makerlab
# 3. Run (install as a systemd service — see actions/runner/docs):
./run.sh
```

Runner prerequisites: Docker + compose v2, Python 3.11+ (with the `venv`
module), Node.js 22, and passwordless sudo for Playwright browser deps
(fallback: browsers pre-installed). Re-register after host rebuilds;
`gh` must be authenticated with owner/admin scope on `dhjh24/modumesh-makerlab`.

### Where backups must live

**Never commit backup artifacts to git.** The `backups/` directory is
git-ignored and untracked — dumps and MinIO objects are frequently large,
contain secrets (DB credentials, tokens, user data), and bloating the
repository history is unrecoverable. Store backups **outside the repo**
(e.g. `/var/backups/modumesh/` on the host, or an off-site/object-storage
target), and keep only scripts/config in the repo.

## Incident response

### Worker crash / memory exhaustion

1. Check logs: `docker logs compose-worker-1 --tail 50`
2. Restart worker: `docker compose -f infra/compose/docker-compose.yml restart worker`
3. If job fails due to memory, increase `memoryMb` in the plugin manifest and rebuild.

### Plugin runs malicious code

1. Disable the plugin immediately (admin-only since the security sprint — requires the admin key):
   `curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" http://localhost:8002/api/v1/plugins/<plugin-id>/disable`
2. Review job logs for the plugin's output files.
3. If network egress was detected, investigate the storage bucket for exfiltrated files.
4. Revoke the author's submission privileges.

### Database migration failure

1. Check the migration log: `docker logs compose-api-1 | grep -i migration`
2. Manually revert the migration: `docker exec compose-api-1 sh -c 'alembic downgrade -1'`
3. Fix the migration script and rebuild.

## Plugin submission moderation

```bash
# Validate a plugin manifest
curl -X POST http://localhost:8002/api/v1/submissions/validate \
  -H 'Content-Type: application/json' \
  -d '{"manifest":...}'

# Run a security scan
curl -X POST http://localhost:8002/api/v1/submissions/security-scan \
  -H 'Content-Type: application/json' \
  -d '{"manifest":...}'
```

## Monitoring

### Metrics endpoint (GM-12 D4.1)

`GET /api/v1/metrics` serves Prometheus text format (internal-only: no host
port published; optionally gated by `API_METRICS_TOKEN`):

```bash
curl -fsS http://localhost:8002/api/v1/metrics | grep modumesh_
```

Metric families:

| Metric | Type | Meaning |
| ------ | ---- | ------- |
| `modumesh_http_requests_total` | Counter | requests by method/route/status |
| `modumesh_job_submissions_total` | Counter | job submissions by job type |
| `modumesh_plugin_execution_duration_seconds` | Histogram | plugin wall-clock time by job type/outcome (worker observes) |
| `modumesh_queue_depth` | Gauge | jobs waiting on the Redis queue |
| `modumesh_active_leases` | Gauge | jobs with a live worker lease |
| `modumesh_job_terminal` | Gauge | terminal jobs (completed/failed/cancelled) by status/job type |

In multiprocess mode (`PROMETHEUS_MULTIPROC_DIR` — set by compose for api +
worker) the endpoint aggregates both processes; `mark_process_dead` on exit
prevents stale files.

### Host health & alert checks (GM-12 D4.3)

`scripts/healthcheck.sh` is designed for a host cron every 5 minutes: exits
non-zero when any check is RED (queue depth > `QUEUE_DEPTH_ALERT` (default
50), failed-jobs gauge > `FAILED_JOBS_ALERT` (default off), API/web
unreachable), so the cron wrapper can alert (mail/ntfy/webhook):

```cron
*/5 * * * * cd /home/dirk/modumesh-makerlab && bash scripts/healthcheck.sh || /usr/local/bin/notify-alert "MakerLab healthcheck RED"
```

Relevant metrics to track:

- Job completion rate (completed vs failed — `modumesh_job_terminal`)
- Job queue depth (Redis list length — `modumesh_queue_depth`)
- Plugin execution duration (`modumesh_plugin_execution_duration_seconds`)
- API response times and error rates (`modumesh_http_requests_total` by status)
- Worker CPU/memory
- MinIO disk usage
- Postgres connection count
