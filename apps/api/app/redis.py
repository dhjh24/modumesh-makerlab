"""Redis async client with startup validation."""

from __future__ import annotations

import time

from redis.asyncio import Redis as AsyncRedis

from app.config import settings

redis_client: AsyncRedis | None = None


async def init_redis() -> AsyncRedis:
    """Create and return the Redis connection pool."""
    global redis_client
    redis_client = AsyncRedis.from_url(
        settings.redis.url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    return redis_client


async def check_redis_connectivity() -> dict:
    """Ping Redis and return status + latency."""
    start = time.monotonic()
    try:
        if redis_client is None:
            return {"status": "not_initialized", "latency_ms": 0}
        pong = await redis_client.ping()
        elapsed = time.monotonic() - start
        if pong:
            return {"status": "ok", "latency_ms": round(elapsed * 1000, 1)}
        return {"status": "error", "latency_ms": round(elapsed * 1000, 1), "error": "ping returned false"}
    except Exception as exc:
        elapsed = time.monotonic() - start
        return {"status": "error", "latency_ms": round(elapsed * 1000, 1), "error": str(exc)}


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
