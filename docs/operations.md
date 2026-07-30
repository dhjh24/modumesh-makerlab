# Operations Guide (Phase 6)

Self-hosted ModuMesh MakerLab operations: deploy, backup, restore, upgrade,
rollback, troubleshooting, and the release checklist.

## Fresh install

1. Copy environment and set **strong** secrets (never use defaults in production):

```bash
cp .env.example .env
# Required in production:
#   POSTGRES_PASSWORD, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
#   API_BOOTSTRAP_ADMIN_PASSWORD, API_DOWNLOAD_SIGNING_SECRET
```

2. Start the production stack (reverse proxy on 80/443 only):

```bash
docker compose -f infra/compose/docker-compose.prod.yml --env-file .env up -d --build
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c /app/alembic.ini upgrade head
```

3. Edit `infra/compose/Caddyfile.prod` hostname + ACME email, then reload proxy.

4. Sign in at `https://<host>/login` with the bootstrap admin user.

5. Open **Admin** → status page for services, queue depth, storage, and plugins.

### Development stack

```bash
cp .env.example .env
make start
make migrate
# Web http://localhost:3000  API http://localhost:8000
# Default admin: admin / change_me_admin  (change immediately)
```

## Authentication model

| Role    | Capabilities                                                                                              |
| ------- | --------------------------------------------------------------------------------------------------------- |
| `owner` | Own projects, jobs, files; catalog read                                                                   |
| `admin` | All of the above + all projects, plugin enable/disable/resync, admin status, retention purge, user create |

Sessions are opaque bearer tokens (hashed at rest) delivered as `Authorization: Bearer` and/or `modumesh_session` HttpOnly cookie. Download links use short-lived HMAC signatures.

## Backup

```bash
chmod +x scripts/*.sh
./scripts/backup.sh
# writes backups/<timestamp>/{postgres.dump,minio/,SHA256SUMS,MANIFEST.txt}

# Production compose:
COMPOSE_FILE=infra/compose/docker-compose.prod.yml \
COMPOSE_PROJECT_NAME=compose \
  ./scripts/backup.sh
```

Schedule via cron or systemd timer. Store backups off-host.

## Restore

```bash
# Stop workers first to avoid writes during restore
docker compose -f infra/compose/docker-compose.yml stop worker api
./scripts/restore.sh backups/<timestamp>
docker compose -f infra/compose/docker-compose.yml start api worker

# Production:
COMPOSE_FILE=infra/compose/docker-compose.prod.yml \
  ./scripts/restore.sh backups/<timestamp>
```

### Automated restore test

```bash
./scripts/test-restore.sh
# Expect: RESTORE_TEST_OK ...
```

## Unresolved residual risks (accepted for standalone RC)

| Risk                               | Mitigation / follow-up                                              |
| ---------------------------------- | ------------------------------------------------------------------- |
| In-process rate limits (not Redis) | Single API replica recommended; sticky proxy if scaled              |
| Public `/metrics` when enabled     | Prefer internal scrape; set `API_METRICS_ENABLED=false` or firewall |
| Plugin network deny is in-process  | Documented sandbox; not a full network namespace                    |
| No OAuth/OIDC                      | Local sessions only (ADR-0004); Phase 7+                            |
| Retention purge is manual          | Cron/call `POST /api/v1/admin/retention/purge`                      |
| Default bootstrap password         | Must change before exposing publicly                                |

## Upgrade

1. Take a backup (`./scripts/backup.sh`).
2. Pull/build new images.
3. Run migrations: `make migrate` (or prod equivalent).
4. Restart API → worker → web → proxy.
5. Verify `/health/ready`, admin status, and a Nameplate smoke job.
6. Keep the previous image tags for rollback.

## Rollback

1. Stop the stack.
2. Redeploy the previous known-good image tags.
3. If a migration is incompatible, restore PostgreSQL from the pre-upgrade backup (`./scripts/restore.sh`).
4. Restore MinIO only if object keys diverged.
5. Confirm `/health/ready` and admin status.

Alembic migrations in this release are additive (auth/sessions/version_locks). Downgrade with `alembic downgrade -1` only on non-production after backup.

## Data retention and deletion

- Soft archive: `POST /api/v1/projects/{id}/archive`
- Hard delete (owner/admin): `DELETE /api/v1/projects/{id}` — removes DB rows (cascade) and MinIO objects
- Retention purge (admin): `POST /api/v1/admin/retention/purge` — deletes archived projects older than `API_RETENTION_DAYS` (default 90; `0` disables)

## Observability

| Endpoint                   | Purpose                                                               |
| -------------------------- | --------------------------------------------------------------------- |
| `GET /health/live`         | Liveness                                                              |
| `GET /health/ready`        | Readiness (Postgres, Redis, MinIO)                                    |
| `GET /health`              | Aggregated dependency status                                          |
| `GET /metrics`             | Prometheus text metrics                                               |
| `GET /api/v1/admin/status` | Admin dashboard data                                                  |
| `X-Correlation-ID`         | Propagated on every API response; included in structured request logs |

## Worker security

Verified constraints (Compose):

- Non-root image user (`modumesh`)
- `read_only: true` root filesystem + `/tmp` tmpfs
- `cap_drop: [ALL]`, `no-new-privileges`
- Memory / CPU / PIDs limits
- Plugins mounted `:ro`
- Plugin subprocess: timeout, memory rlimit, network deny by default

```bash
./scripts/verify-worker-security.sh
# Expect: WORKER_SECURITY_OK
```

## Reverse proxy guidance

- Terminate TLS at Caddy/Nginx/Traefik; do not publish Postgres, Redis, or MinIO.
- Forward `/api/*`, `/health*`, `/metrics` to the API; everything else to the web app.
- Set `API_CORS_ORIGINS` to the public origin only.
- Enable `API_SESSION_COOKIE_SECURE=true` behind HTTPS.

Example Caddyfile: `infra/compose/Caddyfile.prod`.

## Troubleshooting

| Symptom           | Check                                                           |
| ----------------- | --------------------------------------------------------------- |
| 401 on API        | Login; token expired; `API_AUTH_ENABLED`                        |
| 403 on project    | Wrong owner; use admin or correct user                          |
| Jobs stuck queued | Worker logs; Redis; `verify-worker-security` / read-only `/tmp` |
| Download 401      | Use signed URL (`POST .../signed-url`) or session               |
| Ready 503         | Postgres/Redis/MinIO health                                     |
| Rate limit 429    | `API_RATE_LIMIT_PER_MINUTE`                                     |

## Release checklist

- [ ] Strong secrets in `.env` (no defaults)
- [ ] Fresh install + migrate succeeds
- [ ] Login as admin; create second owner user; cross-user access denied
- [ ] Nameplate generate → preview → signed download
- [ ] `./scripts/backup.sh` and `./scripts/test-restore.sh` pass
- [ ] `./scripts/verify-worker-security.sh` passes
- [ ] Admin status shows healthy services
- [ ] Unit, integration, e2e, geometry, security, migration, restore tests green
- [ ] Dependency / container / secret scans: no unresolved critical/high
- [ ] Upgrade + rollback dry-run documented with backup evidence
- [ ] Stop before Phase 7 (no shop integration)
