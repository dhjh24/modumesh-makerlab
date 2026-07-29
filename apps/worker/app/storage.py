"""MinIO object storage for the worker."""

from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from minio import Minio

from app.config import settings

_client: Minio | None = None


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    size_bytes: int
    sha256: str
    content_type: str


def init_minio() -> Minio:
    global _client
    _client = Minio(
        settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        secure=settings.minio.secure,
    )
    if not _client.bucket_exists(settings.minio.bucket):
        _client.make_bucket(settings.minio.bucket)
    return _client


def build_immutable_key(
    *,
    project_id: uuid.UUID | str,
    job_id: uuid.UUID | str,
    filename: str,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    token = uuid.uuid4().hex[:12]
    safe_name = filename.replace("/", "_").replace("..", "_")
    return f"projects/{project_id}/jobs/{job_id}/{ts}_{token}_{safe_name}"


def put_bytes(
    *,
    project_id: uuid.UUID | str,
    job_id: uuid.UUID | str,
    filename: str,
    data: bytes,
    content_type: str = "application/json",
) -> StoredObject:
    if _client is None:
        raise RuntimeError("MinIO client is not initialized")
    object_key = build_immutable_key(
        project_id=project_id, job_id=job_id, filename=filename
    )
    digest = hashlib.sha256(data).hexdigest()
    _client.put_object(
        settings.minio.bucket,
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
