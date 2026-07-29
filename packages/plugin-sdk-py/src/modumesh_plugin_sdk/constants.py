"""SDK versioning and hard limits shared by API, worker, and CLI."""

from __future__ import annotations

CURRENT_SDK_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1"
SUPPORTED_ENGINES = frozenset({"python"})

# Host accepts plugins whose sdkVersion major matches CURRENT_SDK_VERSION.
SDK_COMPAT_MAJOR = int(CURRENT_SDK_VERSION.split(".", 1)[0])

DEFAULT_MAX_INPUT_BYTES = 65_536
DEFAULT_MAX_OUTPUT_BYTES = 1_048_576
ABSOLUTE_MAX_INPUT_BYTES = 10_485_760
ABSOLUTE_MAX_OUTPUT_BYTES = 104_857_600

ALLOWED_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "text/plain",
        "text/csv",
        "application/octet-stream",
        "image/png",
        "model/stl",
        "model/step",
        "model/obj",
        "model/gltf-binary",
    }
)

# Environment variable prefixes never passed into plugin subprocesses.
BLOCKED_ENV_PREFIXES = (
    "POSTGRES_",
    "REDIS_",
    "MINIO_",
    "AWS_",
    "DATABASE_",
    "DB_",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "API_KEY",
    "DOCKER",
)

BLOCKED_ENV_KEYS = frozenset(
    {
        "DATABASE_URL",
        "REDIS_URL",
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "DOCKER_HOST",
        "SSH_AUTH_SOCK",
    }
)
