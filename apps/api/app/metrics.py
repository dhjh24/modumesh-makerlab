"""In-process metrics registry (Prometheus text exposition)."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Optional


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._hist_sum: dict[str, float] = defaultdict(float)
        self._hist_count: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def _key(self, name: str, labels: Optional[dict[str, str]] = None) -> str:
        if not labels:
            return name
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{parts}}}"

    def inc(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += value

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._gauges[self._key(name, labels)] = value

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self._hist_sum[name] += value
            self._hist_count[name] += 1

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            for k, v in sorted(self._counters.items()):
                lines.append(f"{k} {v}")
            for k, v in sorted(self._gauges.items()):
                lines.append(f"{k} {v}")
            for name in sorted(self._hist_sum.keys()):
                lines.append(f"{name}_sum {self._hist_sum[name]}")
                lines.append(f"{name}_count {self._hist_count[name]}")
        return "\n".join(lines) + ("\n" if lines else "")


metrics = MetricsRegistry()
