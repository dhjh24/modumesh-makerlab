#!/usr/bin/env bash
# Restore PostgreSQL and MinIO from a backup directory created by backup.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/infra/compose/docker-compose.yml")
SRC_DIR="${1:?Usage: restore.sh /path/to/backup-dir}"

if [[ ! -f "$SRC_DIR/postgres.dump" ]]; then
  echo "Missing postgres.dump in $SRC_DIR" >&2
  exit 1
fi

echo "==> Restoring PostgreSQL from $SRC_DIR/postgres.dump"
# Terminate connections, drop/recreate DB, restore.
"${COMPOSE[@]}" exec -T postgres \
  psql -U "${POSTGRES_USER:-modumesh}" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB:-modumesh}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${POSTGRES_DB:-modumesh};
CREATE DATABASE ${POSTGRES_DB:-modumesh} OWNER ${POSTGRES_USER:-modumesh};
SQL

"${COMPOSE[@]}" exec -T postgres \
  pg_restore -U "${POSTGRES_USER:-modumesh}" -d "${POSTGRES_DB:-modumesh}" --clean --if-exists \
  < "$SRC_DIR/postgres.dump" || true
# pg_restore exits 1 on some benign warnings; verify table presence:
"${COMPOSE[@]}" exec -T postgres \
  psql -U "${POSTGRES_USER:-modumesh}" -d "${POSTGRES_DB:-modumesh}" -c "SELECT COUNT(*) FROM schema_migrations;"

if [[ -d "$SRC_DIR/minio" ]]; then
  echo "==> Restoring MinIO objects"
  MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-modumesh}"
  MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-change_me_in_production}"
  BUCKET="${MINIO_BUCKET:-modumesh-models}"
  docker run --rm --network "${COMPOSE_PROJECT_NAME:-compose}_default" \
    -v "$SRC_DIR/minio:/backup:ro" \
    --entrypoint /bin/sh \
    minio/mc:latest \
    -c "mc alias set local http://minio:9000 '$MINIO_ACCESS_KEY' '$MINIO_SECRET_KEY' && \
        mc mb --ignore-existing local/$BUCKET && \
        mc mirror --overwrite /backup local/$BUCKET"
fi

echo "==> Restore complete from $SRC_DIR"
