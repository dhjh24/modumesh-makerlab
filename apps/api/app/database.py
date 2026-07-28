"""SQLAlchemy async database setup and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.postgres.dsn,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connectivity() -> dict:
    """Ping the database and return status + latency."""
    import time

    start = time.monotonic()
    try:
        async with async_session_factory() as session:
            await session.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        elapsed = time.monotonic() - start
        return {"status": "ok", "latency_ms": round(elapsed * 1000, 1)}
    except Exception as exc:
        elapsed = time.monotonic() - start
        return {"status": "error", "latency_ms": round(elapsed * 1000, 1), "error": str(exc)}


async def close_db() -> None:
    """Dispose the database connection pool."""
    await engine.dispose()
