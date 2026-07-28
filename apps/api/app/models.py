"""SQLAlchemy metadata — shared models for all migrations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SchemaMigration(Base):
    """Tracks applied database migrations."""
    __tablename__ = "schema_migrations"

    version = Column(Integer, primary_key=True, autoincrement=False)
    description = Column(String(255), nullable=False)
    applied_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    checksum = Column(String(64), nullable=True)
