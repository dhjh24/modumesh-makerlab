#!/usr/bin/env bash
# Restore PostgreSQL and MinIO from a backup directory created by backup.sh.
# Override compose file for production:
#   COMPOSE_FILE=infra/compose/docker-compose.prod.yml ./scripts/restore.sh backups/<stamp>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/infra/compose/docker-compose.yml}"
if [[ "$COMPOSE_FILE" != /* ]]; then
  COMPOSE_FILE="$ROOT/$COMPOSE_FILE"
fi
COMPOSE=(docker compose -f "$COMPOSE_FILE")
SRC_DIR="${1:?Usage: restore.sh /path/to/backup-dir}"

if [[ ! -f "$SRC_DIR/postgres.dump" ]]; then
  echo "Missing postgres.dump in $SRC_DIR" >&2
  exit 1
fi

echo "==> Restoring PostgreSQL from $SRC_DIR/postgres.dump (compose=$COMPOSE_FILE)"
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
  if [[ -z "${MINIO_ACCESS_KEY:-}" || -z "${MINIO_SECRET_KEY:-}" ]]; then
    MINIO_ACCESS_KEY="$("${COMPOSE[@]}" exec -T api printenv MINIO_ACCESS_KEY)"
    MINIO_SECRET_KEY="$("${COMPOSE[@]}" exec -T api printenv MINIO_SECRET_KEY)"
    BUCKET="${MINIO_BUCKET:-$("${COMPOSE[@]}" exec -T api printenv MINIO_BUCKET)}"
  else
    BUCKET="${MINIO_BUCKET:-modumesh-models}"
  fi
  BUCKET="${BUCKET:-modumesh-models}"
  NETWORK="${COMPOSE_NETWORK:-${COMPOSE_PROJECT_NAME:-compose}_default}"
  docker run --rm --network "$NETWORK" \
    -v "$SRC_DIR/minio:/backup:ro" \
    --entrypoint /bin/sh \
    minio/mc:RELEASE.2025-04-16T18-13-26Z \
    -c "mc alias set local http://minio:9000 '$MINIO_ACCESS_KEY' '$MINIO_SECRET_KEY' && \
        mc mb --ignore-existing local/$BUCKET && \
        mc mirror --overwrite /backup local/$BUCKET"
fi

echo "==> Restore complete from $SRC_DIR"
