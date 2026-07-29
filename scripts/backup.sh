#!/usr/bin/env bash
# Backup PostgreSQL and MinIO data for ModuMesh MakerLab.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/infra/compose/docker-compose.yml")
STAMP="${BACKUP_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups/$STAMP}"

mkdir -p "$OUT_DIR"

echo "==> Backing up PostgreSQL to $OUT_DIR/postgres.dump"
"${COMPOSE[@]}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-modumesh}" -d "${POSTGRES_DB:-modumesh}" -Fc \
  > "$OUT_DIR/postgres.dump"

echo "==> Backing up MinIO bucket via mc mirror"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-modumesh}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-change_me_in_production}"
BUCKET="${MINIO_BUCKET:-modumesh-models}"

docker run --rm --network "${COMPOSE_PROJECT_NAME:-compose}_default" \
  -v "$OUT_DIR:/backup" \
  --entrypoint /bin/sh \
  minio/mc:latest \
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
EOF

echo "==> Backup complete: $OUT_DIR"
echo "$OUT_DIR"
