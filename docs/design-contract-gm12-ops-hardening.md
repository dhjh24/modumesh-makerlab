# Ops Hardening: Secrets, Backups, CI/CD, Observability — Design Contract (GM-12)

Author: Technical Architect (orchestrator) · Branch: `agent/gm12-ops-hardening` (stacks after GM-9/10/11 board: PRs #47/#48/#49)
Status: design contract — implementation delegated to `security-appsec-engineer` + `devops-automator` roles when the board merges.

## Goal
Close the operational gaps the 2026-08-14 team audit found but that are **outside** the shipped epics.
GM-9 already landed C1/C2/H1/H4/H7/M14/M15; GM-10 landed auth/RBAC; GM-11 landed the workspace UI.
GM-12 targets the remaining ops cluster (audit refs M16, M17, M18, M19, M20, M21, L2, L3 + the runbook's
unrealized observability claims): **secrets management, automated backups & DR, CI/CD hardening, and a real observability surface.**

Scope: infra (`infra/compose`), API boot/config (`apps/api/app/config.py`, `apps/api/app/main.py`, `apps/api/app/routers/health.py`),
CI (`.github/workflows/ci.yml`), docs (`docs/runbook.md`, `.env.example`). **No plugin or worker-behavior changes** —
sandboxing/zero-trust stays a separate epic (audit M3/M4/M5, effort L).

## Current state (verified 2026-08-14, from the audit + direct read)

| Area | Fact | Source |
|---|---|---|
| Defaults | `POSTGRES_PASSWORD`/`MINIO_SECRET_KEY` default `change_me_in_production`; `ADMIN_PLUGIN_SIGNING_SECRET` default `dev-secret`; Redis has **no requirepass** | config.py:16,50,87; compose:7,34 |
| Compose env | CI copies `.env.example` to repo-root `.env`, but compose project-dir is `infra/compose` → CI stack runs on **default weak creds** | ci.yml:234; audit M20 |
| Backups | No automation: manual `pg_dump` only in runbook; MinIO "should be snapshotted" with no procedure; restore never tested | audit M16; runbook |
| Health | `/health`, `/health/ready`, `/health/live`, `/health/full` exist; **no `/metrics`, no Prometheus, no alerting**; runbook claims metrics that don't exist | health.py:80-147; audit §3 |
| Compose | No resource limits; postgres/redis/minio lack `restart:`; **no healthchecks on api/worker/web** | compose (all services); audit M17 |
| CI hygiene | `pip install --user -e … --break-system-packages` into persistent `$HOME/.local` (cross-job bleed); no npm/pip audit, no osv-scanner, no trivy | ci.yml:109-111,154-156; audit M19 |
| Images | Mutable/unpinned `python:3.11-slim`, `node:22-alpine`, `minio/minio:latest`; compose build lacks `--pull` | audit M18 |
| Exposure | FastAPI `/docs` + `/openapi.json` publicly proxied + API direct on :8002 | audit M21; Caddyfile:51-55 |
| Filename | `files.py:70` interpolates Content-Disposition filename raw (CR/LF injection) | audit L2 |
| Migrations | Alembic runs in-app at every API boot, non-fatally; replicas race, drift silent | main.py:28-41; audit L3 |

## Deliverables

### D1 — Secrets management
1. **Redis requirepass**: compose `redis` service gains `command: redis-server --requirepass ${REDIS_PASSWORD:-…}`; `RedisSettings` gains `password` (env `REDIS_PASSWORD`), URL becomes `redis://:pass@host:port/db`; worker + api consume it. Internal network only — keeps the "no host port" posture, kills unauthenticated access.
2. **Fail-closed boot validation** (extend GM-9's admin check): `Settings` startup refuses when `POSTGRES_PASSWORD`, `MINIO_SECRET_KEY`, or `REDIS_PASSWORD` equal the documented defaults (`change_me_in_production`, `dev-secret`) **and** `ENV != development` (new `API_ENV` setting, default `development` for local; CI sets `API_ENV=ci` which still requires non-default creds per D3).
3. **`.env` wiring**: compose switches to explicit `--env-file infra/compose/.env` (and `.env.example` documents it); CI no longer relies on repo-root `.env` copy (fixes M20 root cause).
4. **`/docs` + `/openapi.json` disabled** when `API_ENV != development` (`docs_url=None, openapi_url=None, redoc_url=None` in `create_app`).
5. **Content-Disposition fix**: `files.py` sanitizes filename (strip CR/LF/control chars, fall back to `model-<id>.<ext>`), + regression test (audit L2).
6. **Alembic as explicit deploy step** (audit L3): remove in-app auto-upgrade (or gate behind `API_RUN_MIGRATIONS=1`); runbook + CI get an explicit `alembic upgrade head` step before API start.

### D2 — Automated backups & DR
1. **`scripts/backup.sh`** (repo, `backups/` remains gitignored, **outside** the repo on the host):
   - `pg_dump -Fc` → timestamped file → `mc cp` to MinIO `modumesh-backups/` bucket (or rclone to a configured remote `BACKUP_TARGET`).
   - `mc mirror` MinIO `modumesh-models` → backup bucket (only changed objects, incremental).
   - Manifest + SHA256SUMS written alongside; **fail loudly** on any step (non-zero exit, alert channel per D4).
2. **Schedule**: compose `backup` service (same image as api, `entrypoint: /scripts/backup.sh`, cron via `docker compose` + host crontab documented in runbook, or a `backup-cron` sidecar). Runs daily; retention `BACKUP_RETENTION_DAYS` (default 14) pruned by script.
3. **Restore drill in CI**: new workflow job `restore-drill` (weekly `schedule`) or manual `workflow_dispatch`: spins the compose stack with an empty volume, restores the latest backup (pg_restore + `mc mirror --overwrite`), asserts health endpoints pass and a sample project's files download — proving the restore path works, not just the dump path.
4. **Runbook**: document restore procedure (step-by-step commands) + where backups live on the host; remove the "should be snapshotted" placeholder.

### D3 — CI/CD hardening
1. **Python venv per job** (audit M19): replace `pip install --user … --break-system-packages` with `python -m venv "$RUNNER_TEMP/venv"` → `"$RUNNER_TEMP/venv/bin/pip install -e …[dev]"` → invoke via `"$RUNNER_TEMP/venv/bin/python -m pytest …"`. No more `$HOME/.local` bleed; add pip cache (`actions/setup-python` cache or `~/.cache/pip`).
2. **Supply-chain gates**: new `supply-chain` job — `osv-scanner` (lockfiles + requirements), `pip-audit` (venv), `npm audit --omit=dev` (apps/web, packages/*), fail on any finding ≥ moderate (allowlist file `security/audit-allowlist.json` for known-false-positives).
3. **Image hygiene** (audit M18): compose builds gain `--pull`; pin `minio/minio:latest` → a concrete digest; document digest-pinning policy for `python`/`node` images in runbook (full pinning tracked via renovate config added in the same PR — `renovate.json` with grouped base-image updates).
4. **Non-default creds assertion in CI** (audit M20): CI generates fresh random secrets (or reads from repo secrets) into `infra/compose/.env` before the smoke stack starts; a `docker compose config` assertion step fails the job if any default secret value appears in the resolved config.
5. **Runner reliability** (post-#47-49 board): document in runbook that the runner must be registered on `ci-1` (100.109.168.32; old `ci` host offline) — one-time ops step, no code.

### D4 — Observability
1. **`GET /api/v1/metrics`** (Prometheus text format, `prometheus-client` — no new heavy deps): counters/gauges for request totals by route+status, job submissions, job terminal states (completed/failed/cancelled) with `job_type` label, queue depth (Redis `LLEN` of the job queue), active leases, plugin execution duration histogram. Auth: internal-only — bound to container network, not published to host (same posture as datastores); optional `API_METRICS_TOKEN` bearer for the scrape.
2. **Healthchecks on api/worker/web** in compose (audit M17): api → `/api/v1/health/ready`; worker → healthcheck exec `python -c "import redis; redis.Redis(...).ping()"` (or worker's own `/healthz` TCP check); web → HTTP check on :3000. Plus `restart: unless-stopped` on postgres/redis/minio and `deploy.resources.limits` (memory) on api/worker (sane defaults: api 512MB, worker 1GB).
3. **Alerting**: `scripts/healthcheck.sh` + runbook-documented host-side checks (or compose `prometheus` + `alertmanager` services, both internal-only) alerting on: queue depth > N for > 5 min, job failure-rate spike, any healthcheck red. Keep it small: the audit's ask is that the runbook's claims become real — a Prometheus container + alert rules file + runbook alert section is the deliverable; Grafana optional (documented, not required to merge).
4. **Structured logging**: confirm `app.logging` emits JSON + `request_id` on all routes (correlation IDs already exist in error responses per runbook); add `request_id` middleware if missing (small, contained).

## Existing building blocks (do NOT reinvent)
- `apps/api/app/logging.py` (`configure_logging`, `get_logger`) — extend, don't replace.
- `apps/api/app/routers/health.py` — health endpoints already wired; add `/metrics` as a sibling router.
- GM-9's `apps/api/app/security/admin.py` boot-validation pattern — extend the same fail-closed mechanism to datastore secrets.
- `infra/compose/docker-compose.yml` healthcheck style (postgres/redis/minio already have them — mirror it for api/worker/web).
- `.env.example` section headers — add REDIS_PASSWORD, API_ENV, BACKUP_* under the existing structure.
- CI: `ci.yml` env block already defines `CI_COMPOSE_PROJECT`/ports — add the `.env` generation + assertion there.

## Guardrails (repo-wide, from .hermes.md / team doc)
- No commits to `main`; work only on `agent/gm12-ops-hardening`.
- No `.env`, no real secrets committed. `.env.example` gains new keys with `change_me_*` placeholders only.
- `backups/` stays gitignored; backup artifacts never enter the repo.
- Internal-only for all new listening surfaces (metrics, Prometheus/Alertmanager): no host port publishing.
- CI must stay green on the self-hosted runner (`ci-1` after board merge); no GitHub-hosted runners.
- Migrations: if D1.6 touches schema at all (it shouldn't — D1 is config/infra), append a new alembic revision; never edit applied ones.
- TypeScript/Python gates unchanged: `npm run typecheck`, pytest suites, prettier.

## Definition of done / acceptance
1. `docker compose config` resolves with **zero default secrets** when `API_ENV != development`; api refuses to boot otherwise (test: boot with default creds → non-zero exit).
2. Redis requires a password in compose + code paths (api + worker connect with it); unauthenticated redis-cli from the api container fails.
3. `scripts/backup.sh` produces a pg_dump + MinIO mirror in the backup target, manifest + checksums, non-zero exit on failure; restore drill job in CI restores from the latest backup and health/full + a file download pass.
4. `/api/v1/metrics` serves Prometheus text; queue-depth and job-terminal counters visible; internal-only binding confirmed.
5. api/worker/web have healthchecks + restart policies; resource limits set on api/worker.
6. `pip-audit`/`osv-scanner`/`npm audit` gate in CI, green on current tree (allowlist only for documented FPs).
7. `/docs` and `/openapi.json` 404 when `API_ENV != development`; Content-Disposition injection test passes.
8. Runbook updated: restore procedure, backup location/retention, alert setup, runner host note; no "should be snapshotted" placeholders left.
9. HANDOFF block complete with state=done and evidence (including the restore drill run).

## Handoff
End each delegation with the `HANDOFF:` block (owner: security-appsec-engineer / devops-automator, state, scope, evidence, changes, tests_required, acceptance, rollback, dependencies, blocker). D2's restore drill and D4's metrics are security-owner; D1's compose/env/CI wiring and D3 are devops-owner; cross-cutting (config.py boot validation) belongs to security-owner with devops review.
