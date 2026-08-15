"""Pydantic request/response schemas for projects, jobs, and files."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None


class ProjectList(BaseModel):
    items: list[ProjectOut]
    total: int


class JobCreate(BaseModel):
    job_type: str = Field(default="sample", max_length=64)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    plugin_version: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Optional plugin version pin. Defaults to latest enabled.",
    )


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    parent_job_id: Optional[UUID] = None
    job_type: str
    status: str
    input_payload: dict[str, Any]
    plugin_version: Optional[str] = None
    progress_pct: int
    progress_message: Optional[str] = None
    error_message: Optional[str] = None
    idempotency_key: Optional[str] = None
    attempt_number: int
    worker_id: Optional[str] = None
    timeout_seconds: int
    cancel_requested: bool
    created_at: datetime
    updated_at: datetime
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobList(BaseModel):
    items: list[JobOut]
    total: int


class JobProgress(BaseModel):
    id: UUID
    status: str
    progress_pct: int
    progress_message: Optional[str] = None
    error_message: Optional[str] = None
    cancel_requested: bool
    updated_at: datetime


class PluginOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plugin_id: str
    version: str
    name: str
    description: Optional[str] = None
    sdk_version: str
    engine: str
    entrypoint: str
    categories: list[Any]
    outputs: list[Any]
    timeout_seconds: int
    memory_mb: int
    network_policy: str
    input_schema: dict[str, Any]
    enabled: bool
    status: str
    diagnostics: Optional[str] = None
    max_input_bytes: int
    max_output_bytes: int
    source_path: str
    discovered_at: datetime
    updated_at: datetime
    # Marketplace fields (GM-1)
    author: Optional[str] = None
    license_id: Optional[str] = None
    license_url: Optional[str] = None
    source_url: Optional[str] = None
    maturity: str = "experimental"
    tags: list[Any] = Field(default_factory=list)
    thumbnail: Optional[str] = None
    capabilities: dict[str, Any] = Field(default_factory=dict)


class PluginList(BaseModel):
    items: list[PluginOut]
    total: int
    issues: list[dict[str, Any]] = Field(default_factory=list)


class PluginSyncResult(BaseModel):
    plugin_dir: str
    discovered: int
    upserted: int
    issues: list[dict[str, Any]]
    items: list[PluginOut]


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    job_id: Optional[UUID] = None
    object_key: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class FileList(BaseModel):
    items: list[FileOut]
    total: int


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor: Optional[str] = None
    details: dict[str, Any]
    created_at: datetime


class ErrorOut(BaseModel):
    detail: str
    code: Optional[str] = None


# ── Auth (GM-10) ───────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: Optional[str] = None
    display_name: str
    is_admin: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut
