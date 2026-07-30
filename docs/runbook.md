# ModuMesh MakerLab — Operator Runbook

This document describes procedures for common operational tasks,
incident response, and recovery.

## Service overview

The MakerLab runs as a set of Docker containers on a single host:

| Service | Port | Description |
|---------|------|-------------|
| API | 8002 (host) → 8000 | FastAPI backend |
| Web | 3002 (host) → 3000 | Next.js frontend |
| Worker | — | Celery-like job worker (Redis queue) |
| Postgres | 5432 | Job/plugin/file metadata |
| Redis | 6379 | Job queue and cache |
| MinIO | 9000/9001 | Object storage (generated files) |

## Health checks

```bash
# Get overall health
curl http://localhost:8002/api/v1/health
curl http://localhost:8002/api/v1/health/full

# Check container status
docker compose -f infra/compose/docker-compose.yml ps
```

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
# Re-scan plugin directories
curl -s -X POST http://localhost:8002/api/v1/plugins/resync

# Enable/disable a plugin
curl -s -X POST http://localhost:8002/api/v1/plugins/nameplate/enable
curl -s -X POST http://localhost:8002/api/v1/plugins/nameplate/disable
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

## Incident response

### Worker crash / memory exhaustion

1. Check logs: `docker logs compose-worker-1 --tail 50`
2. Restart worker: `docker compose -f infra/compose/docker-compose.yml restart worker`
3. If job fails due to memory, increase `memoryMb` in the plugin manifest and rebuild.

### Plugin runs malicious code

1. Disable the plugin immediately: `curl -X POST http://localhost:8002/api/v1/plugins/<plugin-id>/disable`
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
