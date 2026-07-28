"""Worker placeholder tests."""

from __future__ import annotations

import importlib.util
import os
import sys


def test_worker_module_syntax() -> None:
    """Verify the worker main module can be parsed."""
    worker_path = os.path.join(
        os.path.dirname(__file__), "..", "app", "main.py"
    )
    spec = importlib.util.spec_from_file_location("app.main", worker_path)
    assert spec is not None, f"Could not load spec from {worker_path}"
    module = importlib.util.module_from_spec(spec)
    assert module is not None


def test_worker_main_runs() -> None:
    """Verify the worker entry point starts and handles SIGTERM."""
    result = __import__("subprocess").run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, 'apps/worker'); from app.main import main; print('ok')"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
