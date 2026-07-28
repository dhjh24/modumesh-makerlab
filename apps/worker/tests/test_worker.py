"""Worker placeholder tests."""

from __future__ import annotations


def test_worker_config_imports() -> None:
    """Verify the worker config module can be imported."""
    from app.config import Settings, WorkerSettings
    s = Settings()
    assert s.worker.poll_interval_seconds == 5


def test_worker_settings_defaults() -> None:
    """Verify worker settings have sensible defaults."""
    from app.config import WorkerSettings
    ws = WorkerSettings()
    assert ws.concurrency >= 1
    assert ws.poll_interval_seconds >= 1
    assert ws.plugin_timeout_seconds >= 30
    assert ws.max_memory_mb >= 128


def test_worker_redis_config() -> None:
    """Verify Redis URL generation works."""
    from app.config import RedisSettings
    rs = RedisSettings()
    assert rs.host == "localhost"
    assert rs.port == 6379
    assert "redis://" in rs.url
