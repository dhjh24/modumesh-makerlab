"""Redis job queue producer."""

from __future__ import annotations

from app.domain.queue import JOB_QUEUE_KEY, cancel_key
from app import redis as redis_mod


async def enqueue_job(job_id: str) -> None:
    if redis_mod.redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    await redis_mod.redis_client.lpush(JOB_QUEUE_KEY, job_id)


async def signal_cancel(job_id: str, ttl_seconds: int = 3600) -> None:
    """Set a cooperative cancel flag visible to workers."""
    if redis_mod.redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    await redis_mod.redis_client.set(cancel_key(job_id), "1", ex=ttl_seconds)


async def clear_cancel(job_id: str) -> None:
    if redis_mod.redis_client is None:
        return
    await redis_mod.redis_client.delete(cancel_key(job_id))


async def queue_depth() -> int:
    if redis_mod.redis_client is None:
        return 0
    return int(await redis_mod.redis_client.llen(JOB_QUEUE_KEY))
