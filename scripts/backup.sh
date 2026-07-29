#!/usr/bin/env bash
# Backup PostgreSQL and MinIO data for ModuMesh MakerLab.
# Override compose file for production:
#   COMPOSE_FILE=infra/compose/docker-compose.prod.yml ./scripts/backup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/infra/compose/docker-compose.yml}"
if [[ "$COMPOSE_FILE" != /* ]]; then
  COMPOSE_FILE="$ROOT/$COMPOSE_FILE"
fi
COMPOSE=(docker compose -f "$COMPOSE_FILE")
STAMP="${BACKUP_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups/$STAMP}"

mkdir -p "$OUT_DIR"

echo "==> Backing up PostgreSQL to $OUT_DIR/postgres.dump (compose=$COMPOSE_FILE)"
"${COMPOSE[@]}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-modumesh}" -d "${POSTGRES_DB:-modumesh}" -Fc \
  > "$OUT_DIR/postgres.dump"

echo "==> Backing up MinIO bucket via mc mirror"
# Prefer credentials from the running API container so host .env drift cannot break backups.
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
  -v "$OUT_DIR:/backup" \
  --entrypoint /bin/sh \
  minio/mc:RELEASE.2025-04-16T18-13-26Z \
  -c "mc alias set local http://minio:9000 '$MINIO_ACCESS_KEY' '$MINIO_SECRET_KEY' && \
      mc mirror --overwrite local/$BUCKET /backup/minio"

sha256sum "$OUT_DIR/postgres.dump" > "$OUT_DIR/SHA256SUMS"
if [[ -d "$OUT_DIR/minio" ]]; then
  (cd "$OUT_DIR" && find minio -type f -print0 | sort -z | xargs -0 sha256sum) >> "$OUT_DIR/SHA256SUMS"
fi

cat > "$OUT_DIR/MANIFEST.txt" <<EOF
stamp=$STAMP
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
postgres_db=${POSTGRES_DB:-modumesh}
minio_bucket=$BUCKET
compose_file=$COMPOSE_FILE
EOF

echo "==> Backup complete: $OUT_DIR"
echo "$OUT_DIR"
