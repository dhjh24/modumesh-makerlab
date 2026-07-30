#!/usr/bin/env bash
# Security scanning helper for Phase 6 release hardening.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
FAIL=0

echo "==> Python dependency audit (pip-audit)"
python -m pip install -q --upgrade 'pip>=26.1.2' 'setuptools>=83.0.0' 'wheel' 'click>=8.3.3'
if ! command -v pip-audit >/dev/null 2>&1; then
  pip install -q pip-audit
fi
(
  cd "$ROOT"
  pip install -q -e packages/plugin-sdk-py
  cd apps/api && pip install -q -e ".[dev]"
  pip-audit --skip-editable || FAIL=1
)

echo "==> npm audit (production)"
npm audit --omit=dev --audit-level=high || FAIL=1

echo "==> Secret scan (gitleaks)"
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --config .gitleaks.toml --no-git || FAIL=1
else
  docker run --rm -v "$ROOT:/repo" zricethezav/gitleaks:latest \
    detect --source /repo --config /repo/.gitleaks.toml --no-git || FAIL=1
fi

echo "==> Container scan (Trivy) — api image if present"
if command -v trivy >/dev/null 2>&1; then
  IMG="$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E 'api|modumesh' | head -n1 || true)"
  if [[ -n "$IMG" ]]; then
    trivy image --severity HIGH,CRITICAL --exit-code 1 "$IMG" || FAIL=1
  else
    echo "No local image found; skip trivy"
  fi
else
  echo "trivy not installed; skip (install for release)"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "SECURITY_SCAN_FAIL"
  exit 1
fi
echo "SECURITY_SCAN_OK"
