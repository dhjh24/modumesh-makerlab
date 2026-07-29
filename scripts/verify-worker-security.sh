#!/usr/bin/env bash
# Verify worker container security constraints (Phase 6).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/infra/compose/docker-compose.yml")

CID="$("${COMPOSE[@]}" ps -q worker)"
if [[ -z "$CID" ]]; then
  echo "Worker is not running" >&2
  exit 1
fi

echo "==> Inspecting worker $CID"
INSPECT="$(docker inspect "$CID")"

python3 - <<'PY' "$INSPECT"
import json, sys
data = json.loads(sys.argv[1])[0]
hc = data["HostConfig"]
cfg = data["Config"]
errors = []

user = cfg.get("User") or ""
if user in ("", "root", "0", "0:0"):
    errors.append(f"worker runs as root-like user: {user!r}")

if not hc.get("ReadonlyRootfs"):
    errors.append("ReadonlyRootfs is false")

caps = hc.get("CapDrop") or []
if "ALL" not in caps and "all" not in [c.lower() for c in caps]:
    errors.append(f"CapDrop missing ALL: {caps}")

sec = hc.get("SecurityOpt") or []
if not any("no-new-privileges" in s for s in sec):
    errors.append(f"missing no-new-privileges: {sec}")

if not hc.get("Memory") or hc["Memory"] <= 0:
    errors.append("Memory limit not set")

mounts = data.get("Mounts") or []
plugin_mounts = [m for m in mounts if m.get("Destination") == "/plugins"]
if plugin_mounts and plugin_mounts[0].get("RW") is True:
    errors.append("/plugins mount is writable")

if errors:
    print("WORKER_SECURITY_FAIL")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print("WORKER_SECURITY_OK")
print(f" user={user}")
print(f" readonly_rootfs={hc.get('ReadonlyRootfs')}")
print(f" cap_drop={caps}")
print(f" memory={hc.get('Memory')}")
print(f" pids_limit={hc.get('PidsLimit')}")
PY
