"""ModuMesh MakerLab worker — Redis queue consumer for generation jobs.

Phase 2: processes the harmless `sample` job type only. No plugins, no CAD.
"""

from __future__ import annotations

import asyncio
import signal
import uuid
from typing import Optional

from app.config import settings
from app.database import close_db, session_scope
from app.job_ops import claim_job
from app.jobs.sample import run_sample_job
from app.logging import configure_logging, get_logger
from app.queue_keys import JOB_QUEUE_KEY
from app.reaper import reap_expired_leases
from app import redis as redis_mod
from app.redis import check_redis, close_redis, init_redis
from app.storage import init_minio

log = get_logger("worker")


def resolve_worker_id() -> str:
    if settings.worker.worker_id:
        return settings.worker.worker_id
    return f"worker-{uuid.uuid4().hex[:10]}"


async def startup_check() -> dict:
    status: dict = {"redis": {"status": "pending"}, "minio": {"status": "pending"}}
    try:
        await init_redis()
        status["redis"] = await check_redis()
    except Exception as exc:
        status["redis"] = {"status": "error", "error": str(exc)}

    try:
        init_minio()
        status["minio"] = {"status": "ok"}
    except Exception as exc:
        status["minio"] = {"status": "error", "error": str(exc)}

    return status


async def process_job_id(job_id: str, worker_id: str) -> None:
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        log.error("invalid job id on queue", job_id=job_id)
        return

    async with session_scope() as session:
        job = await claim_job(session, job_uuid, worker_id)
        if job is None:
            log.info("job not claimable", job_id=job_id)
            return

        log.info(
            "processing job",
            job_id=job_id,
            job_type=job.job_type,
            attempt=job.attempt_number,
        )

        if job.job_type != "sample":
            from app.job_ops import transition
            from app.states import JobStatus

            await transition(
                session,
                job,
                JobStatus.FAILED,
                worker_id=worker_id,
                error_message=f"Unsupported job_type '{job.job_type}' in Phase 2",
                progress_message="unsupported job type",
            )
            return

        await run_sample_job(session, job, worker_id=worker_id)
        log.info("job finished", job_id=job_id, status=job.status)


async def dequeue_once(timeout: int = 2) -> Optional[str]:
    if redis_mod.redis_client is None:
        return None
    # BRPOP returns (key, value) or None on timeout
    item = await redis_mod.redis_client.brpop(JOB_QUEUE_KEY, timeout=timeout)
    if item is None:
        return None
    _key, job_id = item
    return job_id


async def consumer_loop(
    worker_id: str,
    stop_event: asyncio.Event,
    sem: asyncio.Semaphore,
) -> None:
    while not stop_event.is_set():
        try:
            job_id = await dequeue_once(timeout=settings.worker.poll_interval_seconds)
            if job_id is None:
                continue
            await sem.acquire()

            async def _run(jid: str = job_id) -> None:
                try:
                    await process_job_id(jid, worker_id)
                except Exception as exc:
                    log.exception("job processing error", job_id=jid, error=str(exc))
                finally:
                    sem.release()

            asyncio.create_task(_run())
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("consumer loop error", error=str(exc))
            await asyncio.sleep(1)


async def reaper_loop(worker_id: str, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            count = await reap_expired_leases(worker_id)
            if count:
                log.info("reaper finished", reaped=count)
        except Exception as exc:
            log.warning("reaper error", error=str(exc))
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.worker.reaper_interval_seconds,
            )
        except asyncio.TimeoutError:
            continue


async def main_async() -> None:
    configure_logging(
        log_level=settings.worker.log_level,
        service="modumesh-worker",
    )
    worker_id = resolve_worker_id()
    log.info("worker starting", worker_id=worker_id)

    startup = {"redis": {"status": "pending"}}
    for attempt in range(5):
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

    stop_event = asyncio.Event()
    sem = asyncio.Semaphore(settings.worker.concurrency)

    def _request_shutdown(*_args) -> None:
        log.info("shutdown signal received")
        stop_event.set()

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    consumer = asyncio.create_task(consumer_loop(worker_id, stop_event, sem))
    reaper = asyncio.create_task(reaper_loop(worker_id, stop_event))

    await stop_event.wait()
    consumer.cancel()
    reaper.cancel()
    await asyncio.gather(consumer, reaper, return_exceptions=True)

    await close_redis()
    await close_db()
    log.info("worker stopped")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
