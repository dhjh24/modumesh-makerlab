# ADR-0001: Record Architecture Decisions

**Status:** Accepted

**Date:** 2026-07-28

## Context

The project needs a lightweight, auditable way to capture architectural
decisions so that future contributors (and future selves) understand why
things were done a certain way.

## Decision

We use Architecture Decision Records (ADRs) as described by Michael Nygard
(http://thinkrelevance.com/blog/2011/11/15/documenting-architecture-decisions).

Each ADR:

- Is a short markdown file in `docs/adr/`
- Has a unique sequential number (`NNNN`)
- Records context, decision, and consequences
- Is immutable once accepted — amendments produce a new ADR

## Consequences

- Positive: Clear history of architectural rationale.
- Positive: New contributors can catch up by reading the index.
- Negative: Overhead of writing decisions — kept minimal by limiting to
  consequential architecture choices (not implementation details).
