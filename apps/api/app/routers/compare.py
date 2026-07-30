"""Compare mode API — run one input across multiple generators."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["compare"])


@router.post("/api/v1/compare", status_code=201)
async def create_comparison(
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit the same input to multiple generators for comparison.

    Request body:
    {
      \"project_id\": \"...\",
      \"input_payload\": { ... same params for all generators ... },
      \"generators\": [\"logo-lightbox\", \"nameplate\"]
    }

    Returns a list of queued job IDs, one per generator.
    """
    project_id = body.get("project_id")
    input_payload = body.get("input_payload")
    generators = body.get("generators", [])

    if not project_id or not input_payload or not generators:
        raise HTTPException(status_code=400, detail="project_id, input_payload, and generators are required")
    if len(generators) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 generators per comparison")

    # Verify project exists
    row = (await db.execute(
        text("SELECT id FROM projects WHERE id = :pid"),
        {"pid": project_id},
    )).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    jobs = []
    for gen in generators:
        result = await db.execute(
            text("""
                INSERT INTO generation_jobs (project_id, job_type, input_payload, status)
                VALUES (:pid, :gen, :payload, 'queued')
                RETURNING id
            """),
            {"pid": project_id, "gen": gen, "payload": _json_dumps(input_payload)},
        )
        job_id = result.scalar_one()
        jobs.append({"generator": gen, "job_id": str(job_id)})

    await db.commit()

    return {
        "project_id": project_id,
        "comparison": {"generator_count": len(jobs)},
        "jobs": jobs,
        "note": "Jobs are queued. Poll /api/v1/jobs/{id} for each.",
    }


@router.get("/api/v1/compare/{project_id}")
async def get_comparison_results(
    project_id: UUID,
    generators: str = "",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get comparison results for a project, optionally filtered by generators.

    Returns job status and output files for each generator in the comparison.
    """
    gen_list = [g.strip() for g in generators.split(",") if g.strip()] if generators else []

    if gen_list:
        placeholders = ", ".join(f":g{i}" for i in range(len(gen_list)))
        params = {"pid": project_id, **{f"g{i}": g for i, g in enumerate(gen_list)}}
        rows = (await db.execute(
            text(f"""
                SELECT gj.id, gj.job_type, gj.status, gj.progress_pct, gj.error_message
                FROM generation_jobs gj
                WHERE gj.project_id = :pid AND gj.job_type IN ({placeholders})
                ORDER BY gj.created_at DESC
            """),
            params,
        )).mappings().fetchall()
    else:
        rows = (await db.execute(
            text("""
                SELECT gj.id, gj.job_type, gj.status, gj.progress_pct, gj.error_message
                FROM generation_jobs gj
                WHERE gj.project_id = :pid
                ORDER BY gj.created_at DESC
            """),
            {"pid": project_id},
        )).mappings().fetchall()

    return {
        "project_id": str(project_id),
        "results": [dict(r) for r in rows],
        "total": len(rows),
    }


def _json_dumps(obj):
    import json
    return json.dumps(obj)
