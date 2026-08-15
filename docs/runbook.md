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

### Postgres backup

```bash
docker exec compose-db-1 pg_dump -U modumesh modumesh > makerlab-backup-$(date +%Y%m%d).sql
```

### Postgres restore

```bash
cat makerlab-backup-20260730.sql | docker exec -i compose-db-1 psql -U modumesh modumesh
```

### MinIO data

MinIO uses a local volume. The data directory should be snapshotted
alongside the Postgres dump for a full recovery.

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

Relevant metrics to track:

- Job completion rate (completed vs failed)
- Job queue depth (Redis list length)
- API response times (FastAPI's built-in metrics)
- Worker CPU/memory
- MinIO disk usage
- Postgres connection count
