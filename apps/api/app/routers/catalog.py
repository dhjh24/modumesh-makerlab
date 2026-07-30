"""Catalog API routes for Generator Marketplace.

Provides discovery, filtering, and detail endpoints for the plugin
catalog. Mounted alongside the existing /api/v1/plugins endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import get_logger

router = APIRouter(tags=["catalog"])
log = get_logger("catalog")

# SPDX identifiers that are recognized for catalog visibility
KNOWN_LICENSES = frozenset({
    "MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE",
    "CC0-1.0", "UNLICENSE", "ZLIB", "0BSD",
    "LGPL-2.1-ONLY", "LGPL-2.1-OR-LATER", "LGPL-3.0-ONLY", "LGPL-3.0-OR-LATER",
    "GPL-2.0-ONLY", "GPL-3.0-ONLY", "MPL-2.0",
})


@router.get("/api/v1/catalog")
async def list_catalog(
    category: str | None = Query(None),
    engine: str | None = Query(None),
    maturity: str | None = Query(None),
    capability: str | None = Query(None),
    search: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List marketplace-catalog plugins with optional filters.

    Only returns plugins with status='active' and a known license.
    """
    conditions = [
        "pr.status = 'active'",
        "pr.enabled = true",
    ]

    if category:
        conditions.append(f"pr.categories @> '[{_safe_json_term(category)}]'")
    if engine:
        conditions.append(f"pr.engine = :engine")
    if maturity:
        conditions.append(f"pr.manifest->>'maturity' = :maturity")
    if capability:
        conditions.append(f"pr.manifest->'capabilities'->>:capability = 'true'")
    if search:
        conditions.append(
            f"(pr.name ILIKE :search OR pr.plugin_id ILIKE :search "
            f"OR pr.description ILIKE :search)"
        )

    where = " AND ".join(conditions)

    count_sql = f"SELECT COUNT(*) FROM plugin_registry pr WHERE {where}"
    list_sql = f"""
        SELECT pr.id, pr.plugin_id, pr.version, pr.name, pr.description,
               pr.engine, pr.categories, pr.outputs, pr.timeout_seconds,
               pr.memory_mb, pr.manifest,
               pr.author, pr.license_id, pr.license_url,
               pr.source_url, pr.maturity, pr.tags, pr.thumbnail,
               pr.capabilities, pr.sdk_version, pr.source_path,
               pr.discovered_at, pr.updated_at
        FROM plugin_registry pr
        WHERE {where}
        ORDER BY pr.name ASC
        LIMIT :limit OFFSET :offset
    """

    params: dict = {}
    if category:
        pass  # handled by safe_json_term
    if engine:
        params["engine"] = engine
    if maturity:
        params["maturity"] = maturity
    if capability:
        params["capability"] = capability
    if search:
        params["search"] = f"%{search}%"
    params["limit"] = limit
    params["offset"] = offset

    total = (await db.execute(text(count_sql), params)).scalar() or 0
    rows = (await db.execute(text(list_sql), params)).mappings().all()

    items = [_row_to_catalog_item(r) for r in rows]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/api/v1/catalog/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List distinct categories from active catalog plugins."""
    result = await db.execute(
        text("""
            SELECT DISTINCT jsonb_array_elements_text(pr.categories) AS cat
            FROM plugin_registry pr
            WHERE pr.status = 'active' AND pr.enabled = true
            ORDER BY cat ASC
        """)
    )
    categories = [row[0] for row in result if row[0]]
    return {"categories": categories, "total": len(categories)}


@router.get("/api/v1/catalog/{plugin_id}")
async def get_catalog_item(
    plugin_id: str,
    version: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a single catalog entry by plugin ID."""
    where = "pr.plugin_id = :pid AND pr.status = 'active' AND pr.enabled = true"
    if version:
        where += " AND pr.version = :ver"

    sql = f"""
        SELECT pr.id, pr.plugin_id, pr.version, pr.name, pr.description,
               pr.engine, pr.categories, pr.outputs, pr.timeout_seconds,
               pr.memory_mb, pr.manifest,
               pr.author, pr.license_id, pr.license_url,
               pr.source_url, pr.maturity, pr.tags, pr.thumbnail,
               pr.capabilities, pr.sdk_version, pr.source_path,
               pr.input_schema,
               pr.discovered_at, pr.updated_at
        FROM plugin_registry pr
        WHERE {where}
        ORDER BY array_position(
            ARRAY(SELECT jsonb_array_elements_text(pr.categories)),
            pr.categories->>0
        )
        LIMIT 1
    """
    params: dict = {"pid": plugin_id}
    if version:
        params["ver"] = version

    row = (await db.execute(text(sql), params)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plugin not found in catalog")

    return _row_to_catalog_item(row)


def _safe_json_term(term: str) -> str:
    """Safely quote a JSON string term for use in @> operator."""
    escaped = term.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _row_to_catalog_item(row) -> dict:
    """Convert a plugin_registry row to a catalog response item."""
    manifest = dict(row.get("manifest") or {})
    return {
        "id": str(row["id"]),
        "plugin_id": row["plugin_id"],
        "version": row["version"],
        "name": row["name"],
        "description": row.get("description"),
        "engine": row["engine"],
        "categories": list(row.get("categories") or []),
        "outputs": list(row.get("outputs") or []),
        "timeout_seconds": row["timeout_seconds"],
        "memory_mb": row["memory_mb"],
        "author": row.get("author"),
        "license": row.get("license_id"),
        "license_url": row.get("license_url"),
        "source_url": row.get("source_url"),
        "maturity": row.get("maturity") or "experimental",
        "tags": list(row.get("tags") or []),
        "thumbnail": row.get("thumbnail"),
        "capabilities": dict(row.get("capabilities") or {}),
        "sdk_version": row["sdk_version"],
        "source_path": row["source_path"],
        "input_schema": manifest.get("inputSchema"),
        "discovered_at": row.get("discovered_at").isoformat() if row.get("discovered_at") else None,
        "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
    }
