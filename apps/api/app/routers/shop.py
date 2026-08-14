"""Shop handoff API — pricing, price preview, and Vendure-compatible cart payload."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.security.auth import require_user
from app.services import projects as project_service
from app.services.pricing import build_shop_handoff, calculate_price

router = APIRouter(tags=["shop"])


@router.get("/api/v1/projects/{project_id}/jobs/{job_id}/pricing")
async def get_job_pricing(
    project_id: UUID,
    job_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Calculate price for a completed generation job."""
    project = await project_service.get_owned_project(
        db, project_id, current_user.id
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    job = await _get_job(db, project_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    material_estimate = (job.get("design_json") or {}).get("material_estimate")
    if not material_estimate:
        raise HTTPException(status_code=400, detail="No material estimate available for this job")

    pricing = calculate_price(material_estimate)
    return {
        "job_id": str(job_id),
        "project_id": str(project_id),
        **pricing,
    }


@router.post("/api/v1/projects/{project_id}/jobs/{job_id}/shop-handoff")
async def create_shop_handoff(
    project_id: UUID,
    job_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a Vendure-compatible shop handoff payload."""
    project = await project_service.get_owned_project(
        db, project_id, current_user.id
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    job = await _get_job(db, project_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before shop handoff")

    material_estimate = (job.get("design_json") or {}).get("material_estimate")
    pricing = calculate_price(material_estimate) if material_estimate else {"currency": "USD", "total": 0}
    handoff = build_shop_handoff(
        {"id": project.id, "name": project.name},
        job,
        pricing,
    )

    return {
        "handoff": handoff,
        "pricing": pricing,
        "note": "This payload is Vendure-compatible. No private storage URLs are exposed.",
    }


async def _get_job(db: AsyncSession, project_id: UUID, job_id: UUID) -> dict | None:
    # Join generation_jobs with the job's files and design.json content
    sql = text("""
        SELECT
            gj.id, gj.project_id, gj.status, gj.job_type, gj.plugin_version,
            gj.input_payload, gj.completed_at,
            COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'id', f.id,
                        'filename', f.filename,
                        'object_key', f.object_key,
                        'size_bytes', f.size_bytes,
                        'sha256', f.sha256
                    )
                ) FILTER (WHERE f.id IS NOT NULL),
                '[]'::jsonb
            ) AS files
        FROM generation_jobs gj
        LEFT JOIN files f ON f.job_id = gj.id
        WHERE gj.id = :jid AND gj.project_id = :pid
        GROUP BY gj.id
    """)
    row = (await db.execute(sql, {"jid": job_id, "pid": project_id})).mappings().first()
    if row is None:
        return None

    result = dict(row)
    # Fetch design.json content from MinIO via the storage abstraction
    design_file = next(
        (f for f in result.get("files") or [] if f.get("filename") == "design.json"),
        None,
    )
    if design_file:
        try:
            from app.services.storage import get_bytes
            raw = get_bytes(design_file["object_key"]) if "object_key" in design_file else None
            if raw:
                import json
                result["design_json"] = json.loads(raw)
        except Exception:
            result["design_json"] = None
    return result
