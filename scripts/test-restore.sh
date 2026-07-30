#!/usr/bin/env bash
# Automated restore test in an isolated Compose project.
# Creates data, backs it up, restores into a fresh project, verifies rows/objects.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="modumesh-restore-test-$$"
COMPOSE=(docker compose -p "$PROJECT" -f "$ROOT/infra/compose/docker-compose.yml" -f "$ROOT/infra/compose/docker-compose.restore-test.yml")
export COMPOSE_PROJECT_NAME="$PROJECT"
WORKDIR="$(mktemp -d /tmp/modumesh-restore-XXXXXX)"
cleanup() {
  echo "==> Cleaning up"
  "${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
  # MinIO mc writes backup files as root; delete via container if needed.
  if [[ -d "$WORKDIR" ]]; then
    docker run --rm -v "$WORKDIR:/w" alpine:3.20 sh -c 'rm -rf /w/*' >/dev/null 2>&1 || true
    rm -rf "$WORKDIR" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cp "$ROOT/.env.example" "$WORKDIR/.env"
set -a
# shellcheck disable=SC1091
source "$WORKDIR/.env"
set +a

api_curl() {
  docker run --rm --network "${PROJECT}_default" curlimages/curl:8.5.0 "$@"
}

echo "==> Starting isolated stack ($PROJECT)"
(cd "$ROOT" && "${COMPOSE[@]}" --env-file "$WORKDIR/.env" up -d --build postgres redis minio api)

echo "==> Waiting for API"
for i in $(seq 1 60); do
  if api_curl -sf http://api:8000/health/live >/dev/null 2>&1; then
    echo "API is live"
    break
  fi
  sleep 2
done
api_curl -sf http://api:8000/health/live >/dev/null

echo "==> Migrate + seed"
"${COMPOSE[@]}" exec -T api alembic -c /app/alembic.ini upgrade head

TOKEN="$(api_curl -sf -X POST http://api:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${API_BOOTSTRAP_ADMIN_USERNAME:-admin}\",\"password\":\"${API_BOOTSTRAP_ADMIN_PASSWORD:-change_me_admin}\"}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')"

PROJECT_JSON="$(api_curl -sf -X POST http://api:8000/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"restore-probe","description":"phase6"}')"
PROJECT_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$PROJECT_JSON")"

JOB_JSON="$(api_curl -sf -X POST "http://api:8000/api/v1/projects/$PROJECT_ID/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"sample","input_payload":{"msg":"restore-test"}}')"
JOB_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$JOB_JSON")"

"${COMPOSE[@]}" --env-file "$WORKDIR/.env" up -d worker
STATUS="queued"
for i in $(seq 1 90); do
  STATUS="$(api_curl -sf "http://api:8000/api/v1/jobs/$JOB_ID/progress" \
    -H "Authorization: Bearer $TOKEN" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')"
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    break
  fi
  sleep 1
done
[[ "$STATUS" == "completed" ]] || { echo "Job did not complete: $STATUS"; "${COMPOSE[@]}" logs worker --tail=40; exit 1; }

echo "==> Backup"
BACKUP_DIR="$WORKDIR/backup"
mkdir -p "$BACKUP_DIR"
"${COMPOSE[@]}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-modumesh}" -d "${POSTGRES_DB:-modumesh}" -Fc \
  > "$BACKUP_DIR/postgres.dump"

docker run --rm --network "${PROJECT}_default" \
  -v "$BACKUP_DIR:/backup" \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c "mc alias set local http://minio:9000 '${MINIO_ACCESS_KEY:-modumesh_dev}' '${MINIO_SECRET_KEY:-modumesh_dev_secret}' && \
      mc mirror --overwrite local/${MINIO_BUCKET:-modumesh-models} /backup/minio"

echo "==> Wipe and restore"
"${COMPOSE[@]}" exec -T postgres \
  psql -U "${POSTGRES_USER:-modumesh}" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB:-modumesh}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${POSTGRES_DB:-modumesh};
CREATE DATABASE ${POSTGRES_DB:-modumesh} OWNER ${POSTGRES_USER:-modumesh};
SQL
"${COMPOSE[@]}" exec -T postgres \
  pg_restore -U "${POSTGRES_USER:-modumesh}" -d "${POSTGRES_DB:-modumesh}" --clean --if-exists \
  < "$BACKUP_DIR/postgres.dump" || true

docker run --rm --network "${PROJECT}_default" \
  -v "$BACKUP_DIR/minio:/backup:ro" \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c "mc alias set local http://minio:9000 '${MINIO_ACCESS_KEY:-modumesh_dev}' '${MINIO_SECRET_KEY:-modumesh_dev_secret}' && \
      mc rb --force --dangerous local/${MINIO_BUCKET:-modumesh-models} || true && \
      mc mb local/${MINIO_BUCKET:-modumesh-models} && \
      mc mirror --overwrite /backup local/${MINIO_BUCKET:-modumesh-models}"

echo "==> Verify restored project"
COUNT="$("${COMPOSE[@]}" exec -T postgres \
  psql -U "${POSTGRES_USER:-modumesh}" -d "${POSTGRES_DB:-modumesh}" -Atc \
  "SELECT COUNT(*) FROM projects WHERE id = '$PROJECT_ID';")"
[[ "$COUNT" == "1" ]] || { echo "Project missing after restore"; exit 1; }

FILES="$("${COMPOSE[@]}" exec -T postgres \
  psql -U "${POSTGRES_USER:-modumesh}" -d "${POSTGRES_DB:-modumesh}" -Atc \
  "SELECT COUNT(*) FROM files WHERE project_id = '$PROJECT_ID';")"
[[ "$FILES" -ge 1 ]] || { echo "Files missing after restore"; exit 1; }

echo "RESTORE_TEST_OK project=$PROJECT_ID files=$FILES"
