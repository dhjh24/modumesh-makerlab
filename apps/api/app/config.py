"""Central settings and environment validation.

All environment variables are validated via pydantic-settings on startup.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    db: str = "modumesh"
    user: str = "modumesh"
    password: str = "change_me_in_production"

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @property
    def sync_dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    # Optional requirepass (GM-12 D1.1). Empty in development; when set, the
    # URL carries the password so api + worker authenticate on connect.
    password: str = ""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    @property
    def url(self) -> str:
        if self.password:
            from urllib.parse import quote

            return (
                f"redis://:{quote(self.password, safe='')}"
                f"@{self.host}:{self.port}/{self.db}"
            )
        return f"redis://{self.host}:{self.port}/{self.db}"


class MinIOSettings(BaseSettings):
    endpoint: str = "localhost:9000"
    access_key: str = "modumesh"
    secret_key: str = "change_me_in_production"
    bucket: str = "modumesh-models"
    secure: bool = False

    model_config = SettingsConfigDict(env_prefix="MINIO_")


class APISettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3002"
    log_level: str = "info"
    version: str = "0.1.0"
    plugin_dir: str = "/plugins"
    # Deployment environment: "development" (default, local) or anything else
    # (ci/staging/production). Non-development enables fail-closed boot
    # validation of datastore secrets and disables /docs + /openapi.json.
    api_env: str = "development"
    # Run `alembic upgrade head` in-process at boot. Off by default — D1.6
    # makes migrations an explicit deploy step (API_RUN_MIGRATIONS=1).
    run_migrations: bool = False
    # Optional bearer token for GET /api/v1/metrics (API_METRICS_TOKEN).
    # Empty = scrape without auth (internal network only).
    metrics_token: str = ""
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 60
    job_rate_limit_rpm: int = 10
    # Comma-separated CIDR list of trusted reverse proxies. When non-empty,
    # X-Forwarded-For is only trusted from these peers; default empty means
    # the header is never trusted and request.client.host is used directly.
    trusted_proxies: str = ""
    # Lifetime of opaque bearer tokens issued by /api/v1/auth/register|login.
    token_ttl_hours: int = 24

    model_config = SettingsConfigDict(env_prefix="API_")


class WorkerSettings(BaseSettings):
    concurrency: int = 2
    poll_interval_seconds: int = 5
    plugin_timeout_seconds: int = 300
    max_memory_mb: int = 512

    model_config = SettingsConfigDict(env_prefix="WORKER_")


class AdminSettings(BaseSettings):
    plugin_signing_secret: str = "dev-secret"
    admin_api_key: str = ""

    model_config = SettingsConfigDict(env_prefix="ADMIN_")


class Settings(BaseSettings):
    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()
    minio: MinIOSettings = MinIOSettings()
    api: APISettings = APISettings()
    admin: AdminSettings = AdminSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Values that must never survive into a non-development deployment. Postgres
# and MinIO default to them in code; REDIS_PASSWORD has no default value but
# an empty password is indistinguishable from "requirepass not configured".
_DEFAULT_DATABASE_SECRET = "change_me_in_production"


def validate_boot_secrets(
    *,
    api_env: str,
    postgres_password: str,
    minio_secret_key: str,
    redis_password: str,
) -> None:
    """Fail-closed datastore secret validation (GM-12 D1.2).

    In any non-development environment, refuse to boot while a datastore is
    still protected by a documented default (or no) credential. This extends
    GM-9's unconditional admin fail-closed check; ``api_env`` is deliberately
    NOT part of the admin condition — admin endpoints stay fail-closed
    everywhere.

    Raises RuntimeError naming every offending variable; returns None when
    the configuration is acceptable.
    """
    if api_env == "development":
        return
    offenders: list[str] = []
    if postgres_password in ("", _DEFAULT_DATABASE_SECRET):
        offenders.append("POSTGRES_PASSWORD")
    if minio_secret_key in ("", _DEFAULT_DATABASE_SECRET):
        offenders.append("MINIO_SECRET_KEY")
    if not redis_password or redis_password in ("", _DEFAULT_DATABASE_SECRET):
        offenders.append("REDIS_PASSWORD")
    if offenders:
        raise RuntimeError(
            "Refusing to start: API_ENV is not 'development' but datastore "
            "secrets are still at their default/empty values: "
            + ", ".join(offenders)
            + ". Generate strong random values (e.g. `openssl rand -hex 32`) "
            "and set them before deploying."
        )


settings = Settings()
