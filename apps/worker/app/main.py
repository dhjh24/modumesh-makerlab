"""ModuMesh MakerLab worker — queued CAD generation.

The worker polls Redis for queued generation jobs and executes them
via registered plugins.  Jobs run with resource limits, timeouts, and
no network access by default.
"""

from __future__ import annotations

import asyncio
import signal

from app.config import settings
from app.logging import configure_logging, get_logger
from app.redis import check_redis, close_redis, init_redis

LOG_INTERVAL = settings.worker.poll_interval_seconds


async def startup_check() -> dict:
    """Run startup validations and return connectivity status."""
    status = {"redis": {"status": "pending"}}

    try:
        await init_redis()
        status["redis"] = await check_redis()
    except Exception as exc:
        status["redis"] = {"status": "error", "error": str(exc)}

    return status


async def main_async() -> None:
    """Async worker main loop."""
    configure_logging(
        log_level=settings.worker.log_level,
        service="modumesh-worker",
    )
    log = get_logger("worker")

    # ── Startup with Redis retry ─────────────────────────────────────
    startup = {"redis": {"status": "pending"}}
    for attempt in range(3):
        startup = await startup_check()
        if startup.get("redis", {}).get("status") == "ok":
            log.info("worker startup complete", connectivity=startup)
            break
        log.warning(
            "startup check failed, retrying",
            attempt=attempt + 1,
            connectivity=startup,
        )
        await asyncio.sleep(2)
    else:
        log.warning("worker starting with degraded connectivity", connectivity=startup)

    # ── Main loop ────────────────────────────────────────────────────
    def shutdown() -> None:
        log.info("received SIGTERM, shutting down")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, lambda *_: shutdown())

    try:
        while True:
            log.debug("worker heartbeat — no jobs queued (placeholder)")
            await asyncio.sleep(LOG_INTERVAL)
    except asyncio.CancelledError:
        log.info("worker cancelled")
    finally:
        await close_redis()
        log.info("worker stopped")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
