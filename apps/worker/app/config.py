"""Worker settings and environment validation."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    concurrency: int = 2
    poll_interval_seconds: int = 2
    plugin_timeout_seconds: int = 300
    max_memory_mb: int = 512
    log_level: str = "info"
    lease_seconds: int = 30
    heartbeat_interval_seconds: int = 10
    reaper_interval_seconds: int = 15
    sample_step_delay_ms: int = 200
    worker_id: str = ""

    model_config = SettingsConfigDict(env_prefix="WORKER_")


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


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


class MinIOSettings(BaseSettings):
    endpoint: str = "localhost:9000"
    access_key: str = "modumesh"
    secret_key: str = "change_me_in_production"
    bucket: str = "modumesh-models"
    secure: bool = False

    model_config = SettingsConfigDict(env_prefix="MINIO_")


class Settings(BaseSettings):
    worker: WorkerSettings = WorkerSettings()
    redis: RedisSettings = RedisSettings()
    postgres: PostgresSettings = PostgresSettings()
    minio: MinIOSettings = MinIOSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
