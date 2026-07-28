"""MinIO client with startup validation."""

from __future__ import annotations

import io
import time

from minio import Minio

from app.config import settings

minio_client: Minio | None = None


def init_minio() -> Minio:
    """Create and return the Minio client."""
    global minio_client
    minio_client = Minio(
        settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        secure=settings.minio.secure,
    )
    # Ensure the configured bucket exists
    if not minio_client.bucket_exists(settings.minio.bucket):
        minio_client.make_bucket(settings.minio.bucket)
    return minio_client


def check_minio_connectivity() -> dict:
    """Ping MinIO and return status + latency."""
    start = time.monotonic()
    try:
        if minio_client is None:
            return {"status": "not_initialized", "latency_ms": 0}
        bucket = settings.minio.bucket
        exists = minio_client.bucket_exists(bucket)
        elapsed = time.monotonic() - start
        if exists:
            return {"status": "ok", "latency_ms": round(elapsed * 1000, 1)}
        return {"status": "error", "latency_ms": round(elapsed * 1000, 1), "error": f"bucket '{bucket}' not found"}
    except Exception as exc:
        elapsed = time.monotonic() - start
        return {"status": "error", "latency_ms": round(elapsed * 1000, 1), "error": str(exc)}


async def minio_write_test() -> dict:
    """Write and read back a test object to verify MinIO works end-to-end."""
    try:
        if minio_client is None:
            return {"status": "not_initialized"}
        bucket = settings.minio.bucket
        object_name = f"_health_check/test_ping_{int(time.time())}.txt"
        data = b"ModuMesh MakerLab connectivity test"
        data_size = len(data)

        start = time.monotonic()
        minio_client.put_object(
            bucket,
            object_name,
            io.BytesIO(data),
            data_size,
            content_type="text/plain",
        )
        write_elapsed = time.monotonic() - start

        # Read back
        start = time.monotonic()
        response = minio_client.get_object(bucket, object_name)
        read_data = response.read()
        read_elapsed = time.monotonic() - start
        response.close()
        response.release_conn()

        success = read_data == data
        return {
            "status": "ok" if success else "data_mismatch",
            "write_ms": round(write_elapsed * 1000, 1),
            "read_ms": round(read_elapsed * 1000, 1),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
