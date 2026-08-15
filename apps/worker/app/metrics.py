"""Worker-side Prometheus metrics (GM-12 D4.1).

The worker observes ``modumesh_plugin_execution_duration_seconds`` and, when
``PROMETHEUS_MULTIPROC_DIR`` is set (compose shared volume), writes it to the
directory the API's ``/api/v1/metrics`` endpoint aggregates with
``MultiProcessCollector``. Without the env var these observations go nowhere
observable (single-process dev) — harmless.
"""

from __future__ import annotations

import atexit
import os

from prometheus_client import Histogram, multiprocess

MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR")

# Must match the API's histogram (same name + labels) so multiprocess
# aggregation merges them into one series.
PLUGIN_DURATION = Histogram(
    "modumesh_plugin_execution_duration_seconds",
    "Wall-clock time spent executing a plugin subprocess, by job type and outcome",
    ["job_type", "outcome"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)


def _mark_process_dead() -> None:
    """Exclude this process's metric files once it exits (multiprocess mode)."""
    if MULTIPROC_DIR:
        try:
            multiprocess.mark_process_dead(os.getpid())
        except Exception:  # noqa: BLE001 — best-effort on shutdown
            pass


atexit.register(_mark_process_dead)
