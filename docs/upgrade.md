# Upgrade Guide

1. Announce maintenance window.
2. `./scripts/backup.sh` and copy artifacts off-host.
3. Record current image digests / git SHA.
4. Deploy new images (`docker compose ... build && up -d`).
5. Run Alembic: `alembic upgrade head` inside the API container.
6. Smoke: `/health/ready`, admin login, one Nameplate job, signed download.
7. Monitor logs (`X-Correlation-ID`) and `/metrics` for 30–60 minutes.

If smoke fails, follow [Rollback Guide](./rollback.md).
