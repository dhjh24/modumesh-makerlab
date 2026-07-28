"""Redis client module for the worker."""

from __future__ import annotations

from redis.asyncio import Redis as AsyncRedis

from app.config import settings

redis_client: AsyncRedis | None = None


async def init_redis() -> AsyncRedis:
    global redis_client
    redis_client = AsyncRedis.from_url(
        settings.redis.url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    return redis_client


async def check_redis() -> dict:
    import time
    start = time.monotonic()
    try:
        if redis_client is None:
            return {"status": "not_initialized", "latency_ms": 0}
        pong = await redis_client.ping()
        elapsed = time.monotonic() - start
        if pong:
            return {"status": "ok", "latency_ms": round(elapsed * 1000, 1)}
        return {"status": "error", "latency_ms": round(elapsed * 1000, 1)}
    except Exception as exc:
        elapsed = time.monotonic() - start
        return {"status": "error", "latency_ms": round(elapsed * 1000, 1), "error": str(exc)}


async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
