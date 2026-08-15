"""SQLAlchemy ORM models for ModuMesh MakerLab.

Tables: users, projects, generation_jobs, files, audit_events,
plugin_registry, plus schema_migrations (Phase 1).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class SchemaMigration(Base):
    """Tracks applied database migrations (Phase 1)."""

    __tablename__ = "schema_migrations"

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class User(Base):
    """Application user with password-based bearer-token auth (GM-10)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    # Email is nullable so the legacy local-owner row (created by
    # ``ensure_default_owner``) can stay email-less.
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="local-owner")
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=_utcnow,
    )

    projects: Mapped[list[Project]] = relationship(back_populates="owner")
    tokens: Mapped[list[AuthToken]] = relationship(back_populates="user")


class AuthToken(Base):
    """Opaque bearer token for a user.

    Only the SHA-256 hex digest of the raw token is stored; the raw token is
    handed to the client exactly once at issue time and can never be recovered
    from the database.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="tokens")

    __table_args__ = (
        Index("ix_auth_tokens_user_id", "user_id"),
        Index("ix_auth_tokens_token_hash", "token_hash"),
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=_utcnow,
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    owner: Mapped[User] = relationship(back_populates="projects")
    jobs: Mapped[list[GenerationJob]] = relationship(back_populates="project")
    files: Mapped[list[FileObject]] = relationship(back_populates="project")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_projects_status"),
        Index("ix_projects_owner_id", "owner_id"),
        Index("ix_projects_status", "status"),
    )


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'sample'")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'created'")
    )
    input_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    progress_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    worker_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("60")
    )
    plugin_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=_utcnow,
    )
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="jobs")
    parent_job: Mapped[Optional[GenerationJob]] = relationship(
        remote_side="GenerationJob.id",
        foreign_keys=[parent_job_id],
    )
    files: Mapped[list[FileObject]] = relationship(
        back_populates="job",
        foreign_keys="FileObject.job_id",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'created','queued','running','validating','uploading',"
            "'completed','failed','cancelled'"
            ")",
            name="ck_generation_jobs_status",
        ),
        CheckConstraint("progress_pct >= 0 AND progress_pct <= 100", name="ck_jobs_progress"),
        CheckConstraint("attempt_number >= 1", name="ck_jobs_attempt"),
        Index("ix_generation_jobs_project_id", "project_id"),
        Index("ix_generation_jobs_status", "status"),
        Index("ix_generation_jobs_parent_job_id", "parent_job_id"),
        Index("ix_generation_jobs_lease_expires_at", "lease_expires_at"),
        Index(
            "uq_jobs_project_idempotency",
            "project_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "ix_generation_jobs_job_type_plugin_version",
            "job_type",
            "plugin_version",
        ),
    )


class PluginRegistryEntry(Base):
    """Discovered plugin versions with persisted enable/disable state."""

    __tablename__ = "plugin_registry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sdk_version: Mapped[str] = mapped_column(String(32), nullable=False)
    engine: Mapped[str] = mapped_column(String(32), nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(255), nullable=False)
    categories: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    outputs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    network_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'deny'")
    )
    input_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_path: Mapped[str] = mapped_column(String(512), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'active'")
    )
    diagnostics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_input_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("65536")
    )
    max_output_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1048576")
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=_utcnow,
    )
    # Marketplace fields (GM-1)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    license_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    license_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    maturity: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'experimental'")
    )
    tags: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    thumbnail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    capabilities: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'invalid', 'incompatible', 'duplicate', 'quarantined')",
            name="ck_plugin_registry_status",
        ),
        CheckConstraint(
            "network_policy IN ('deny', 'allow')",
            name="ck_plugin_registry_network",
        ),
        Index("ix_plugin_registry_plugin_id", "plugin_id"),
        Index("ix_plugin_registry_enabled", "enabled"),
        Index("ix_plugin_registry_status", "status"),
        Index("ix_plugin_registry_maturity", "maturity"),
        Index("ix_plugin_registry_license", "license_id"),
    )


class FileObject(Base):
    """Immutable object-storage reference with SHA-256 checksum."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("'application/octet-stream'")
    )
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    project: Mapped[Project] = relationship(back_populates="files")
    job: Mapped[Optional[GenerationJob]] = relationship(
        back_populates="files",
        foreign_keys=[job_id],
    )

    __table_args__ = (
        Index("ix_files_project_id", "project_id"),
        Index("ix_files_job_id", "job_id"),
        Index("ix_files_sha256", "sha256"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_created_at", "created_at"),
    )
