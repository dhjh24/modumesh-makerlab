#!/usr/bin/env bash
# ModuMesh MakerLab — automated backup (GM-12 D2.1).
#
# Backs up Postgres (pg_dump -Fc) and mirrors the MinIO models bucket into a
# dedicated backup bucket, writing a manifest + SHA256SUMS alongside. Fails
# loudly (non-zero exit + FATAL message) on any step. Idempotent and safe to
# run from cron: every artifact is timestamped, uploads are additive, and
# retention prunes only artifacts older than BACKUP_RETENTION_DAYS.
#
# Requires: pg_dump, mc (MinIO client), python3 (for remote retention).
#
# Environment:
#   PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE   Postgres connection
#   MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY  MinIO credentials
#   MINIO_BUCKET             source models bucket (default modumesh-models)
#   BACKUP_TARGET            mc alias name (default modumesh) — or set
#                            MC_HOST_<ALIAS_UPPER> to skip alias config
#   BACKUP_DIR               local staging dir (default /var/backups/modumesh)
#   BACKUP_RETENTION_DAYS    prune artifacts older than N days (default 14)
#   PRUNE_ONLY=1             run only the retention prune and exit
set -euo pipefail

PGHOST=${PGHOST:-localhost}
PGPORT=${PGPORT:-5432}
PGUSER=${PGUSER:-modumesh}
PGDATABASE=${PGDATABASE:-modumesh}
MINIO_ENDPOINT=${MINIO_ENDPOINT:-localhost:9000}
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-}
MINIO_BUCKET=${MINIO_BUCKET:-modumesh-models}
BACKUP_TARGET=${BACKUP_TARGET:-modumesh}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/modumesh}
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}
BACKUP_BUCKET="modumesh-backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="${BACKUP_DIR}/postgres-${STAMP}.dump"
MANIFEST_FILE="${BACKUP_DIR}/manifest-${STAMP}.txt"
CHECKSUMS_FILE="${BACKUP_DIR}/SHA256SUMS-${STAMP}.txt"

log() { echo "[backup $(date -u +%FT%TZ)] $*"; }
fail() { echo "[backup FATAL] $*" >&2; exit 1; }

# ── Preconditions ─────────────────────────────────────────────────────────
command -v mc >/dev/null 2>&1 || fail "mc (MinIO client) not found — install it (https://min.io/docs/minio/linux/reference/minio-mc.html)"
command -v python3 >/dev/null 2>&1 || fail "python3 not found — required for remote retention pruning"

# ── Retention prune (also runnable standalone via PRUNE_ONLY=1) ──────────
prune_local() {
    log "pruning local artifacts older than ${BACKUP_RETENTION_DAYS} days in ${BACKUP_DIR}"
    mkdir -p "$BACKUP_DIR"
    find "$BACKUP_DIR" -type f \( \
        -name 'postgres-*.dump' -o \
        -name 'manifest-*.txt' -o \
        -name 'SHA256SUMS-*.txt' \) \
        -mtime "+${BACKUP_RETENTION_DAYS}" -delete
}

prune_remote() {
    log "pruning ${BACKUP_TARGET}/${BACKUP_BUCKET}/postgres/ older than ${BACKUP_RETENTION_DAYS} days"
    # A missing postgres/ prefix (first run) is not an error: yield no keys.
    { mc ls --recursive --json "${BACKUP_TARGET}/${BACKUP_BUCKET}/postgres/" 2>/dev/null || true; } \
        | BACKUP_RETENTION_DAYS="$BACKUP_RETENTION_DAYS" python3 -c '
import json, os, sys
from datetime import datetime, timedelta, timezone
cutoff = datetime.now(timezone.utc) - timedelta(days=int(os.environ["BACKUP_RETENTION_DAYS"]))
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except ValueError:
        continue
    key = obj.get("key", "")
    if not (key.startswith("postgres-") and key.endswith(".dump")):
        continue
    stamp = key[len("postgres-"):-len(".dump")]
    try:
        ts = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        continue
    if ts < cutoff:
        print(key)
' | while read -r key; do
        log "pruning ${key}"
        mc rm "${BACKUP_TARGET}/${BACKUP_BUCKET}/postgres/${key}" || fail "failed to remove ${key}"
    done
}

if [ "${PRUNE_ONLY:-0}" = "1" ]; then
    # Retention is also useful standalone (cron, pre-deploy); the alias must
    # be configured first, so credentials are required here too.
    [ -n "$MINIO_ACCESS_KEY" ] || fail "MINIO_ACCESS_KEY is not set — refusing to prune without credentials"
    [ -n "$MINIO_SECRET_KEY" ] || fail "MINIO_SECRET_KEY is not set — refusing to prune without credentials"
    prune_local
    prune_remote
    log "prune complete"
    exit 0
fi

# ── Credential preconditions (fail loudly BEFORE touching anything) ──────
[ -n "${PGPASSWORD:-}" ] || fail "PGPASSWORD is not set — refusing to back up without credentials"
[ -n "$MINIO_ACCESS_KEY" ] || fail "MINIO_ACCESS_KEY is not set — refusing to back up without credentials"
[ -n "$MINIO_SECRET_KEY" ] || fail "MINIO_SECRET_KEY is not set — refusing to back up without credentials"

command -v pg_dump >/dev/null 2>&1 || fail "pg_dump not found — install postgresql-client (host cron) or use an image that has it"

mkdir -p "$BACKUP_DIR"

# ── mc alias (MC_HOST_<ALIAS> overrides MINIO_* endpoint config) ─────────
alias_var="MC_HOST_$(printf '%s' "$BACKUP_TARGET" | tr '[:lower:]' '[:upper:]')"
if [ -z "${!alias_var:-}" ]; then
    log "configuring mc alias ${BACKUP_TARGET} -> ${MINIO_ENDPOINT}"
    mc alias set "$BACKUP_TARGET" "http://${MINIO_ENDPOINT}" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null \
        || fail "failed to configure mc alias ${BACKUP_TARGET}"
fi

log "ensuring backup bucket ${BACKUP_BUCKET} exists"
mc mb --ignore-existing "${BACKUP_TARGET}/${BACKUP_BUCKET}" >/dev/null 2>&1 || true

# ── Postgres dump ─────────────────────────────────────────────────────────
log "pg_dump -Fc ${PGDATABASE} -> ${DUMP_FILE}"
pg_dump -Fc -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f "$DUMP_FILE" \
    || fail "pg_dump failed — no backup written for this run"

# ── Upload dump + mirror models (additive / incremental) ─────────────────
log "uploading dump to ${BACKUP_TARGET}/${BACKUP_BUCKET}/postgres/"
mc cp "$DUMP_FILE" "${BACKUP_TARGET}/${BACKUP_BUCKET}/postgres/" >/dev/null \
    || fail "failed to upload ${DUMP_FILE}"

log "mirroring ${MINIO_BUCKET} -> ${BACKUP_BUCKET}/models (incremental)"
mc mirror --overwrite "${BACKUP_TARGET}/${MINIO_BUCKET}" "${BACKUP_TARGET}/${BACKUP_BUCKET}/models" \
    || fail "mc mirror failed"

# ── Manifest + checksums (local + remote) ────────────────────────────────
DUMP_SIZE="$(stat -c %s "$DUMP_FILE" 2>/dev/null || stat -f %z "$DUMP_FILE")"
{
    echo "backup_id=${STAMP}"
    echo "created_at=$(date -u +%FT%TZ)"
    echo "pg_dump_file=postgres/${DUMP_FILE##*/}"
    echo "pg_dump_size_bytes=${DUMP_SIZE}"
    echo "source_bucket=${MINIO_BUCKET}"
    echo "backup_bucket=${BACKUP_BUCKET}"
    echo "retention_days=${BACKUP_RETENTION_DAYS}"
} > "$MANIFEST_FILE"
(cd "$BACKUP_DIR" && sha256sum "${DUMP_FILE##*/}" > "$CHECKSUMS_FILE")

log "uploading manifest + checksums"
mc cp "$MANIFEST_FILE" "${BACKUP_TARGET}/${BACKUP_BUCKET}/manifests/" >/dev/null \
    || fail "failed to upload manifest"
mc cp "$CHECKSUMS_FILE" "${BACKUP_TARGET}/${BACKUP_BUCKET}/manifests/" >/dev/null \
    || fail "failed to upload checksums"

# ── Retention ─────────────────────────────────────────────────────────────
prune_local
prune_remote

log "backup complete: ${STAMP} (dump ${DUMP_SIZE} bytes)"
