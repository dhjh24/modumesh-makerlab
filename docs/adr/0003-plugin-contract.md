# ADR-0003: Plugin Contract and Registry

**Status:** Accepted

**Date:** 2026-07-28

## Context

Phase 3 introduces third-party generators. Plugins are untrusted and must not
receive infrastructure credentials. The host needs a versioned contract,
directory discovery, enable/disable persistence, and a controlled runner
integrated with the Phase 2 job queue.

## Decision

1. **Manifest schema v1** (`plugin.manifest.json`) is the source of truth for
   capability declarations (timeout, memory, network, outputs, SDK version).
2. **Python SDK package** `modumesh-plugin-sdk` provides validation, discovery,
   `PluginContext`, subprocess execution, and `modumesh-plugin-check`.
3. **Registry** syncs the plugin directory into PostgreSQL table
   `plugin_registry`, preserving enable/disable across rediscovery.
4. **Jobs** use `job_type = plugin.id` and record immutable `plugin_version`
   plus `input_payload` at creation time.
5. **Compatibility**: host accepts `sdkVersion` with the same major as the
   shipped SDK (`1.x`). Manifest `schemaVersion` must be `"1"`.
6. **Security**: read-only plugin source, per-job work dir, network deny by
   default, credential scrubbing, no Docker socket mount, size and output
   declaration enforcement.

## Consequences

- Positive: New plugins appear via directory drop + resync without frontend
  changes.
- Positive: Authors can validate locally with the contract CLI (also in CI).
- Negative: Network isolation is best-effort (socket monkey-patch + env scrub)
  rather than a full seccomp sandbox; stronger isolation can layer later.
- Negative: Memory limits rely on `RLIMIT_AS` where available.
