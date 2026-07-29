# Release Checklist (Standalone RC)

Use before tagging a release candidate. Stop before Phase 7.

## Functional

- [ ] Fresh install (prod compose) + migrations
- [ ] Upgrade from prior RC + migrations
- [ ] Backup + restore + `scripts/test-restore.sh`
- [ ] Rollback dry-run
- [ ] Nameplate success flow (generate, preview, download)
- [ ] Project hard delete + retention purge

## Security

- [ ] Authz: owner cannot access another user’s projects/files
- [ ] Admin-only plugin mutation + status
- [ ] Signed download URLs expire
- [ ] Worker security script `WORKER_SECURITY_OK`
- [ ] Rate limit + request size limit smoke
- [ ] Security headers present on API responses
- [ ] Dependency scan (pip-audit / npm audit) — no unresolved critical/high
- [ ] Container scan (Trivy) — no unresolved critical/high
- [ ] Secret scan (gitleaks) clean

## Quality gates

- [ ] Unit (API, worker, plugin SDK, Nameplate geometry)
- [ ] Integration smoke (Phase 2–5 + Phase 6 authz)
- [ ] E2E + a11y
- [ ] Migration applies cleanly on empty DB

## Approval

- [ ] Ops docs reviewed (`docs/operations.md`)
- [ ] Unresolved risks documented (see residual risks table in `docs/operations.md`)
- [ ] Release owner sign-off

**Stop before Phase 7** (shop integration / public API freeze).
