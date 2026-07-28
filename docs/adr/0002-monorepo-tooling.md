# ADR-0002: Monorepo Tooling

**Status:** Accepted

**Date:** 2026-07-28

## Context

ModuMesh MakerLab has multiple applications (web, API, worker) and shared
packages (plugin-sdk, shared-types, viewer, ui). We need a monorepo
strategy that works without additional infrastructure.

## Decision

- **npm workspaces** for TypeScript/JavaScript packages (native, no extra
  tooling).
- **pip** with `pyproject.toml` for Python packages (API, worker, plugins).
- **Docker Compose** for service orchestration in development and production.
- No Turborepo, Nx, or Lerna — keep the toolchain minimal until scaling
  demands otherwise.
- No `uv` or `poetry` — standard pip is sufficient for the current scope.

## Consequences

- Positive: Zero additional tooling to install — npm 10+ and Python 3.11+
  are the only requirements.
- Positive: Each app and package remains independently buildable.
- Negative: No centralized task orchestration (no `turbo run` parallel
  builds). CI scripts handle parallelism explicitly.
