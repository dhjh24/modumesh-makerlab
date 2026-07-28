"""ModuMesh MakerLab worker entry point.

The worker polls Redis for queued generation jobs and executes them
via registered plugins.  Jobs run with resource limits, timeouts, and
no network access by default.
"""

from __future__ import annotations

import os
import signal
import time

LOG_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "5"))


def _handle_sigterm(signum: int, frame: object) -> None:
    print("worker: received SIGTERM, shutting down")
    raise SystemExit(0)


signal.signal(signal.SIGTERM, _handle_sigterm)


def main() -> None:
    print(f"worker: started (poll interval={LOG_INTERVAL}s)")
    try:
        while True:
            print("worker: heartbeat — no jobs queued (placeholder)")
            time.sleep(LOG_INTERVAL)
    except SystemExit:
        print("worker: stopped")


if __name__ == "__main__":
    main()
