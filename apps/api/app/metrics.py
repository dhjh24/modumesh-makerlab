"""Prometheus metric definitions for the MakerLab API (GM-12 D4.1).

Metric objects live here (not in the router) so the request middleware
(``app.main``) and the job service (``app.services.jobs``) can increment them
without importing router code. The worker observes
``modumesh_plugin_execution_duration_seconds`` from its own process — see
``apps/worker/app/metrics.py``.

Multi-process support: when ``PROMETHEUS_MULTIPROC_DIR`` is set (compose
mounts a shared volume in api + worker), prometheus-client writes per-process
metric files to that directory and ``collect_registry()`` aggregates them via
``MultiProcessCollector``. Without the env var (unit tests, plain local run)
everything uses the default in-process registry.
"""

from __future__ import annotations

import atexit
import os

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR")

# ── HTTP request totals by route template + status (middleware) ─────────
HTTP_REQUESTS = Counter(
    "modumesh_http_requests_total",
    "HTTP requests served, by method, route template and status code",
    ["method", "route", "status"],
)

# ── Job lifecycle (API service layer) ───────────────────────────────────
JOB_SUBMISSIONS = Counter(
    "modumesh_job_submissions_total",
    "Generation jobs submitted through the API, by job type",
    ["job_type"],
)

# ── Plugin execution (observed by the worker process) ───────────────────
# Registered here too so the metric family is always present in a scrape
# even before the first plugin run. Multiprocess mode merges the worker's
# observations; single-process mode this stays at zero until the API itself
# observes (it doesn't — the worker does).
PLUGIN_DURATION = Histogram(
    "modumesh_plugin_execution_duration_seconds",
    "Wall-clock time spent executing a plugin subprocess, by job type and outcome",
    ["job_type", "outcome"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)

# ── Scrape-time gauges (set by the metrics router) ──────────────────────
QUEUE_DEPTH = Gauge(
    "modumesh_queue_depth",
    "Jobs currently waiting on the Redis job queue (LLEN of the job queue key)",
)
ACTIVE_LEASES = Gauge(
    "modumesh_active_leases",
    "Jobs with a live worker lease (lease_expires_at in the future)",
)
JOB_TERMINAL = Gauge(
    "modumesh_job_terminal",
    "Jobs in a terminal state (completed/failed/cancelled) in the database, by status and job type",
    ["status", "job_type"],
)


def _mark_process_dead() -> None:
    """Exclude this process's metric files once it exits (multiprocess mode)."""
    if MULTIPROC_DIR:
        try:
            multiprocess.mark_process_dead(os.getpid())
        except Exception:  # noqa: BLE001 — best-effort on shutdown
            pass


atexit.register(_mark_process_dead)


def collect_registry() -> bytes:
    """Serialize all metrics in Prometheus text format (aggregated across
    processes when multiprocess mode is active)."""
    if MULTIPROC_DIR:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest()
