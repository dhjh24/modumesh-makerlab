"""Plugin registry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import PluginList, PluginOut, PluginSyncResult
from app.security.admin import require_admin
from app.services import plugins as plugin_service

router = APIRouter(tags=["plugins"])


@router.get("/api/v1/plugins", response_model=PluginList)
async def list_plugins(
    enabled_only: bool = Query(False),
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> PluginList:
    items = await plugin_service.list_plugins(
        db, enabled_only=enabled_only, include_inactive=include_inactive
    )
    return PluginList(
        items=[PluginOut.model_validate(i) for i in items],
        total=len(items),
    )


@router.post("/api/v1/plugins/resync", response_model=PluginSyncResult)
async def resync_plugins(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
) -> PluginSyncResult:
    """Rescan the plugin directory and upsert the registry. Admin-only."""
    summary = await plugin_service.sync_registry(db, actor="api")
    items = await plugin_service.list_plugins(db, include_inactive=True)
    return PluginSyncResult(
        plugin_dir=summary["plugin_dir"],
        discovered=summary["discovered"],
        upserted=summary["upserted"],
        issues=summary["issues"],
        items=[PluginOut.model_validate(i) for i in items],
    )


@router.get("/api/v1/plugins/{plugin_id}", response_model=PluginOut)
async def get_plugin(
    plugin_id: str,
    version: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PluginOut:
    entry = await plugin_service.get_plugin(db, plugin_id, version)
    if entry is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return PluginOut.model_validate(entry)


@router.post(
    "/api/v1/plugins/{plugin_id}/versions/{version}/enable",
    response_model=PluginOut,
)
async def enable_plugin(
    plugin_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
) -> PluginOut:
    """Enable a plugin version. Admin-only (control-plane operation)."""
    entry = await plugin_service.get_plugin(db, plugin_id, version)
    if entry is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    if entry.status != "active":
        raise HTTPException(
            status_code=409, detail=f"Cannot enable plugin in status={entry.status}"
        )
    entry = await plugin_service.set_enabled(db, entry, True)
    return PluginOut.model_validate(entry)


@router.post(
    "/api/v1/plugins/{plugin_id}/versions/{version}/disable",
    response_model=PluginOut,
)
async def disable_plugin(
    plugin_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
) -> PluginOut:
    """Disable a plugin version. Admin-only (control-plane operation)."""
    entry = await plugin_service.get_plugin(db, plugin_id, version)
    if entry is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    entry = await plugin_service.set_enabled(db, entry, False)
    return PluginOut.model_validate(entry)
