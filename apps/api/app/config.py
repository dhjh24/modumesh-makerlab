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

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    @property
    def url(self) -> str:
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
    cors_origins: str = "http://localhost:3000"
    log_level: str = "info"
    version: str = "0.1.0"
    plugin_dir: str = "/plugins"
    # Auth / sessions
    auth_enabled: bool = True
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "change_me_admin"
    session_ttl_hours: int = 24
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    # Signing secret for temporary download URLs (override in production).
    download_signing_secret: str = "change_me_download_secret"
    download_url_ttl_seconds: int = 300
    # Rate / size limits
    rate_limit_per_minute: int = 120
    rate_limit_auth_per_minute: int = 20
    max_request_bytes: int = 1_048_576
    # Retention (days); 0 disables automatic purge scheduling hints
    retention_days: int = 90
    metrics_enabled: bool = True

    model_config = SettingsConfigDict(env_prefix="API_")


class WorkerSettings(BaseSettings):
    concurrency: int = 2
    poll_interval_seconds: int = 5
    plugin_timeout_seconds: int = 300
    max_memory_mb: int = 512

    model_config = SettingsConfigDict(env_prefix="WORKER_")


class Settings(BaseSettings):
    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()
    minio: MinIOSettings = MinIOSettings()
    api: APISettings = APISettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
