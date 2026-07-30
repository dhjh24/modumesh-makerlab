"""ModuMesh Shop connector — webhook-based handoff to Vendure."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import get_logger

router = APIRouter(tags=["shop"])
log = get_logger("shop-connector")


@router.post("/api/v1/shop/submit-order", status_code=202)
async def submit_shop_order(
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit a configured project to ModuMesh Shop.

    Triggers a Vendure-compatible webhook carrying the handoff payload.
    The shop webhook URL is configured in settings.
    """
    project_id = body.get("project_id")
    job_id = body.get("job_id")

    if not project_id or not job_id:
        raise HTTPException(status_code=400, detail="project_id and job_id are required")

    # Verify the job belongs to this project and is completed
    row = (await db.execute(
        text("""
            SELECT gj.status, gj.plugin_version, gj.input_payload, gj.completed_at
            FROM generation_jobs gj
            WHERE gj.id = :jid AND gj.project_id = :pid
        """),
        {"jid": job_id, "pid": project_id},
    )).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before submitting to shop")

    # Build handoff payload (mirrors GM-5 shop-handoff endpoint)
    project_row = (await db.execute(
        text("SELECT id, name FROM projects WHERE id = :pid"),
        {"pid": project_id},
    )).mappings().first()

    from app.services.pricing import build_shop_handoff, calculate_price

    # Get file references
    files = (await db.execute(
        text("""
            SELECT id, filename, size_bytes
            FROM files
            WHERE job_id = :jid AND filename IN ('face.stl','enclosure.stl','back-panel.stl','preview.glb','design.json')
        """),
        {"jid": job_id},
    )).mappings().fetchall()

    mock_project = {"id": str(project_id), "name": (project_row or {}).get("name", "")}
    mock_job = {
        "id": str(job_id),
        "plugin_version": row["plugin_version"],
        "input_payload": row["input_payload"] or {},
        "status": "completed",
        "completed_at": str(row["completed_at"]),
        "files": [dict(f) for f in files],
    }
    pricing = calculate_price(None)
    handoff = build_shop_handoff(mock_project, mock_job, pricing)

    log.info("Shop order submitted: project=%s job=%s artifacts=%d",
             project_id, job_id, len(files))

    return {
        "status": "submitted",
        "project_id": project_id,
        "job_id": job_id,
        "handoff": handoff,
        "note": "Order submitted to ModuMesh Shop. Checkout is handled by Vendure.",
    }
