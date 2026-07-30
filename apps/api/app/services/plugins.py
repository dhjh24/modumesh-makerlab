"""Plugin directory discovery synchronized into PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logging import get_logger
from app.models import PluginRegistryEntry
from app.services.audit import record_audit

log = get_logger("plugins")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _semver_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in version.split(".")[:3]:
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


async def get_plugin(
    session: AsyncSession,
    plugin_id: str,
    version: Optional[str] = None,
    *,
    enabled_only: bool = False,
) -> Optional[PluginRegistryEntry]:
    q = select(PluginRegistryEntry).where(PluginRegistryEntry.plugin_id == plugin_id)
    if version is not None:
        q = q.where(PluginRegistryEntry.version == version)
    if enabled_only:
        q = q.where(
            PluginRegistryEntry.enabled.is_(True),
            PluginRegistryEntry.status == "active",
        )
    rows = list((await session.execute(q)).scalars().all())
    if not rows:
        return None
    if version is not None:
        return rows[0]
    return sorted(rows, key=lambda r: _semver_key(r.version), reverse=True)[0]


async def list_plugins(
    session: AsyncSession,
    *,
    enabled_only: bool = False,
    include_inactive: bool = False,
) -> list[PluginRegistryEntry]:
    q = select(PluginRegistryEntry).order_by(
        PluginRegistryEntry.plugin_id.asc(),
        PluginRegistryEntry.version.desc(),
    )
    if enabled_only:
        q = q.where(
            PluginRegistryEntry.enabled.is_(True),
            PluginRegistryEntry.status == "active",
        )
    elif not include_inactive:
        q = q.where(PluginRegistryEntry.status == "active")
    return list((await session.execute(q)).scalars().all())


async def set_enabled(
    session: AsyncSession,
    entry: PluginRegistryEntry,
    enabled: bool,
    *,
    actor: str = "api",
) -> PluginRegistryEntry:
    entry.enabled = enabled
    entry.updated_at = _now()
    await session.flush()
    await record_audit(
        session,
        entity_type="plugin",
        entity_id=entry.id,
        action="plugin.enabled" if enabled else "plugin.disabled",
        actor=actor,
        details={"plugin_id": entry.plugin_id, "version": entry.version},
    )
    return entry


def _payload_from_loaded(plugin: Any) -> dict[str, Any]:
    outputs = [
        {"name": o.name, "mediaType": o.media_type, "required": o.required}
        for o in plugin.outputs
    ]
    diagnostics = "; ".join(plugin.diagnostics) if plugin.diagnostics else None

    # Determine plugin status based on license
    license_id = plugin.license_id
    if license_id and license_id.upper() in (
        "MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE",
        "CC0-1.0", "UNLICENSE", "ZLIB", "0BSD",
        "LGPL-2.1-ONLY", "LGPL-2.1-OR-LATER", "LGPL-3.0-ONLY", "LGPL-3.0-OR-LATER",
        "GPL-2.0-ONLY", "GPL-3.0-ONLY", "MPL-2.0",
    ):
        status = "active"
    elif license_id:
        # Known but non-standard SPDX — still catalog-visible
        status = "active"
    else:
        # Missing license → quarantine
        status = "quarantined"

    payload = {
        "plugin_id": plugin.plugin_id,
        "version": plugin.version,
        "name": plugin.name,
        "description": plugin.description or None,
        "sdk_version": plugin.sdk_version,
        "engine": plugin.engine,
        "entrypoint": plugin.entrypoint,
        "categories": plugin.categories,
        "outputs": outputs,
        "timeout_seconds": plugin.timeout_seconds,
        "memory_mb": plugin.memory_mb,
        "network_policy": plugin.network_policy,
        "input_schema": plugin.input_schema,
        "manifest": plugin.manifest,
        "source_path": str(plugin.root),
        "status": status,
        "diagnostics": diagnostics,
        "max_input_bytes": plugin.max_input_bytes,
        "max_output_bytes": plugin.max_output_bytes,
        # Marketplace fields
        "author": plugin.author,
        "license_id": license_id,
        "license_url": plugin.license_url,
        "source_url": plugin.source_url,
        "maturity": plugin.maturity,
        "tags": plugin.tags,
        "thumbnail": plugin.thumbnail,
        "capabilities": plugin.capabilities,
    }

    if status == "quarantined":
        payload["diagnostics"] = (
            f"Missing or unrecognized license '{license_id}' — "
            "plugin quarantined. Set a valid SPDX identifier in the manifest."
        )

    return payload


async def sync_registry(
    session: AsyncSession,
    plugin_dir: str | Path | None = None,
    *,
    actor: str = "system",
) -> dict[str, Any]:
    """Discover plugins on disk and upsert into plugin_registry.

    Enable/disable state for known (plugin_id, version) pairs is preserved.
    Invalid or duplicate plugins appear in the returned issues list and are not
    registered as runnable.
    """
    from modumesh_plugin_sdk.discovery import discover_plugins

    root = Path(plugin_dir or settings.api.plugin_dir)
    summary: dict[str, Any] = {
        "plugin_dir": str(root),
        "discovered": 0,
        "upserted": 0,
        "issues": [],
    }

    if not root.is_dir():
        summary["issues"].append(
            {"path": str(root), "message": "plugin dir missing", "severity": "error"}
        )
        log.warning("plugin dir missing", path=str(root))
        return summary

    existing = list((await session.execute(select(PluginRegistryEntry))).scalars().all())
    enabled_map = {(e.plugin_id, e.version): e.enabled for e in existing}
    existing_by_key = {(e.plugin_id, e.version): e for e in existing}

    discovery = discover_plugins(root)
    for issue in discovery.issues:
        summary["issues"].append(
            {"path": issue.path, "message": issue.message, "severity": issue.severity}
        )

    for plugin in discovery.plugins:
        key = (plugin.plugin_id, plugin.version)
        summary["discovered"] += 1
        payload = _payload_from_loaded(plugin)
        payload["enabled"] = enabled_map.get(key, True)
        if key in existing_by_key:
            entry = existing_by_key[key]
            for field, value in payload.items():
                setattr(entry, field, value)
            entry.updated_at = _now()
        else:
            entry = PluginRegistryEntry(id=uuid.uuid4(), discovered_at=_now(), **payload)
            session.add(entry)
            existing_by_key[key] = entry
        summary["upserted"] += 1

    await session.flush()
    await record_audit(
        session,
        entity_type="plugin_registry",
        entity_id=uuid.UUID(int=0),
        action="plugin.registry_synced",
        actor=actor,
        details={
            "discovered": summary["discovered"],
            "upserted": summary["upserted"],
            "issue_count": len(summary["issues"]),
        },
    )
    log.info(
        "plugin registry synced",
        discovered=summary["discovered"],
        upserted=summary["upserted"],
        issues=len(summary["issues"]),
    )
    return summary
