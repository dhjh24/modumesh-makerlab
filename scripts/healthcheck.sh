#!/usr/bin/env bash
# ModuMesh MakerLab — host-side health & alert checks (GM-12 D4.3).
#
# Intended for a host cron job (every 5 minutes). Exits non-zero when any
# check is RED, so the cron entry can alert (e.g. a mail/ntfy/webhook
# wrapper). Prints the state of every check regardless.
#
# Environment:
#   API_URL                default http://localhost:8002
#   WEB_URL                default http://localhost:3002
#   QUEUE_DEPTH_ALERT      alert when queued jobs exceed this (default 50)
#   FAILED_JOBS_ALERT      alert when the failed-jobs gauge exceeds this
#                          (default 0 = no alert on the cumulative counter;
#                          set e.g. 20 and pair with failure-rate trend)
#   METRICS_TOKEN          API_METRICS_TOKEN if the deployment sets one
set -euo pipefail

API_URL=${API_URL:-http://localhost:8002}
WEB_URL=${WEB_URL:-http://localhost:3002}
QUEUE_DEPTH_ALERT=${QUEUE_DEPTH_ALERT:-50}
FAILED_JOBS_ALERT=${FAILED_JOBS_ALERT:-0}
METRICS_TOKEN=${METRICS_TOKEN:-}

red=0
note() { echo "[healthcheck $(date -u +%FT%TZ)] $*"; }
red_alert() { note "RED: $*"; red=1; }

# ── API liveness + readiness ─────────────────────────────────────────────
if curl -fsS --max-time 5 "${API_URL}/api/v1/health/live" >/dev/null 2>&1; then
    note "api /health/live: ok"
else
    red_alert "api /health/live unreachable (${API_URL})"
fi

if curl -fsS --max-time 5 "${API_URL}/api/v1/health/ready" >/dev/null 2>&1; then
    note "api /health/ready: ok"
else
    red_alert "api /health/ready not ready (deps degraded or API down)"
fi

# ── Web ──────────────────────────────────────────────────────────────────
if curl -fsS --max-time 5 "${WEB_URL}/api/health" >/dev/null 2>&1; then
    note "web :3000: ok"
else
    red_alert "web unreachable (${WEB_URL})"
fi

# ── Queue depth + failure gauge from /api/v1/metrics ────────────────────
metrics_url="${API_URL}/api/v1/metrics"
if [ -n "$METRICS_TOKEN" ]; then
    metrics_body="$(curl -fsS --max-time 5 -H "Authorization: Bearer ${METRICS_TOKEN}" "$metrics_url" 2>/dev/null || true)"
else
    metrics_body="$(curl -fsS --max-time 5 "$metrics_url" 2>/dev/null || true)"
fi

if [ -n "$metrics_body" ]; then
    queue_depth="$(printf '%s\n' "$metrics_body" | awk '/^modumesh_queue_depth / {print $2; exit}')"
    queue_depth="${queue_depth:-0}"
    note "queue depth: ${queue_depth} (alert > ${QUEUE_DEPTH_ALERT})"
    if [ "$queue_depth" -gt "$QUEUE_DEPTH_ALERT" ]; then
        red_alert "queue depth ${queue_depth} exceeds ${QUEUE_DEPTH_ALERT} — jobs are backing up"
    fi

    # modumesh_job_terminal{status="failed",...} — cumulative; the trend
    # (delta between consecutive runs) is the failure-rate signal.
    failed="$(printf '%s\n' "$metrics_body" \
        | awk -F'[{" ]+' '/^modumesh_job_terminal/ && /status="failed"/ {gsub(/[^0-9]/,"",$NF); print $NF; exit}')"
    failed="${failed:-0}"
    note "failed jobs (cumulative): ${failed}"
    if [ "$FAILED_JOBS_ALERT" -gt 0 ] && [ "$failed" -gt "$FAILED_JOBS_ALERT" ]; then
        red_alert "failed-jobs gauge ${failed} exceeds ${FAILED_JOBS_ALERT}"
    fi

    leases="$(printf '%s\n' "$metrics_body" | awk '/^modumesh_active_leases / {print $2; exit}')"
    leases="${leases:-0}"
    note "active leases: ${leases}"
else
    red_alert "metrics endpoint returned nothing (${metrics_url})"
fi

if [ "$red" -eq 0 ]; then
    note "all checks passed"
    exit 0
fi
exit 1
