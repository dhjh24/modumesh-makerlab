# ADR-0004: Local session auth for standalone release

- Status: Accepted
- Date: 2026-07-28

## Context

Phase 6 requires authentication suitable for initial self-hosting, owner/admin
roles, and resource-level access checks, without beginning a public API freeze
or shop identity federation.

## Decision

- Use local username/password accounts with bcrypt password hashes.
- Roles: `owner` (own projects) and `admin` (all projects + plugin/ops controls).
- Opaque session tokens stored as SHA-256 hashes in PostgreSQL; presented via
  `Authorization: Bearer` and/or HttpOnly `modumesh_session` cookie.
- Bootstrap admin credentials from environment on first start.
- Temporary downloads use HMAC-signed URLs with short TTL (and optional MinIO
  presign redirect).

## Consequences

- Existing anonymous API access is removed; clients and tests must authenticate.
- Operators must rotate bootstrap secrets before exposing a host.
- OAuth/OIDC federation is deferred past the standalone RC.
