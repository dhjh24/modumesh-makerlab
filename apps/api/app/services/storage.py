"""Object storage abstraction with immutable keys and SHA-256 checksums."""

from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app import minio as minio_mod


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    size_bytes: int
    sha256: str
    content_type: str


def build_immutable_key(
    *,
    project_id: uuid.UUID | str,
    job_id: uuid.UUID | str,
    filename: str,
) -> str:
    """Build an immutable object key that never overwrites prior outputs.

    Format: projects/{project_id}/jobs/{job_id}/{utc_ts}_{uuid}_{filename}
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    token = uuid.uuid4().hex[:12]
    safe_name = filename.replace("/", "_").replace("..", "_")
    return f"projects/{project_id}/jobs/{job_id}/{ts}_{token}_{safe_name}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put_bytes(
    *,
    project_id: uuid.UUID | str,
    job_id: uuid.UUID | str,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> StoredObject:
    """Upload bytes to MinIO under an immutable key; return metadata + checksum."""
    if minio_mod.minio_client is None:
        raise RuntimeError("MinIO client is not initialized")

    object_key = build_immutable_key(
        project_id=project_id, job_id=job_id, filename=filename
    )
    digest = sha256_bytes(data)
    bucket = settings.minio.bucket
    minio_mod.minio_client.put_object(
        bucket,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
        metadata={"sha256": digest, "job_id": str(job_id)},
    )
    return StoredObject(
        object_key=object_key,
        size_bytes=len(data),
        sha256=digest,
        content_type=content_type,
    )


def get_bytes(object_key: str) -> bytes:
    if minio_mod.minio_client is None:
        raise RuntimeError("MinIO client is not initialized")
    response = minio_mod.minio_client.get_object(settings.minio.bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def object_exists(object_key: str) -> bool:
    if minio_mod.minio_client is None:
        raise RuntimeError("MinIO client is not initialized")
    try:
        minio_mod.minio_client.stat_object(settings.minio.bucket, object_key)
        return True
    except Exception:
        return False
