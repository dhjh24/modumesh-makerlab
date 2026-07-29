# Security Policy

## Supported Versions

| Version | Supported       |
| ------- | --------------- |
| 0.x     | ✅ (active dev) |

## Reporting a Vulnerability

**Do not open a public issue.** Report vulnerabilities privately by emailing
the repository owner or opening a [GitHub Security Advisory](https://github.com/dhjh24/modumesh-makerlab/security/advisories).

You should receive a response within 48 hours. If you don't, follow up.

## Disclosure

We follow coordinated disclosure: we fix the issue first, then publish the
advisory after a patch is available.

## Standalone hardening (Phase 6)

Operators should:

- Change all default secrets before exposing a host (`API_BOOTSTRAP_ADMIN_PASSWORD`,
  `API_DOWNLOAD_SIGNING_SECRET`, database and MinIO credentials).
- Keep Postgres, Redis, and MinIO off the public network; terminate TLS at a reverse proxy.
- Run `./scripts/security-scan.sh` and `./scripts/verify-worker-security.sh` before release.
- Follow `docs/operations.md` and `docs/release-checklist.md`.

