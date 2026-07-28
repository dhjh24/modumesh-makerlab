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


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    parent_job_id: Optional[UUID] = None
    job_type: str
    status: str
    input_payload: dict[str, Any]
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
