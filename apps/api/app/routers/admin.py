"""Community plugin release controls — signing, compatibility, admin."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.logging import get_logger

router = APIRouter(tags=["admin"])
log = get_logger("plugin-admin")


# ── Signing ───────────────────────────────────────────────────────────

def _compute_plugin_checksum(manifest: dict[str, Any]) -> str:
    """Compute SHA-256 checksum from the plugin manifest JSON."""
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _verify_signature(checksum: str, signature: str) -> bool:
    """Verify HMAC-SHA256 signature using the configured admin secret."""
    secret = settings.plugin_signing_secret or "dev-secret"
    expected = hmac.new(
        secret.encode(), checksum.encode(), hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Admin endpoints ──────────────────────────────────────────────────

@router.post("/api/v1/admin/plugins/{plugin_id}/sign")
async def sign_plugin(
    plugin_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
) -> dict:
    """Sign a plugin manifest with HMAC-SHA256.

    Admin-only. Requires admin API key in Authorization header.
    """
    if not authorization or not _verify_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")

    manifest = body.get("manifest", {})
    checksum = _compute_plugin_checksum(manifest)
    secret = settings.admin.plugin_signing_secret or "dev-secret"
    signature = hmac.new(
        secret.encode(), checksum.encode(), hashlib.sha256,
    ).hexdigest()

    # Store signature in DB
    await db.execute(
        text("""
            UPDATE plugin_registry
            SET diagnostics = jsonb_set(
                COALESCE(diagnostics, '{}'::jsonb),
                '{signature}',
                :sig::jsonb
            )
            WHERE plugin_id = :pid
        """),
        {"pid": plugin_id, "sig": json.dumps(signature)},
    )
    await db.commit()

    return {
        "plugin_id": plugin_id,
        "checksum": checksum,
        "signature": signature,
        "algorithm": "hmac-sha256",
    }


@router.get("/api/v1/admin/plugins")
async def list_all_plugins(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
) -> dict:
    """List all plugins with admin metadata (signatures, review status)."""
    if not authorization or not _verify_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")

    rows = (await db.execute(
        text("""
            SELECT plugin_id, version, name, author, status, enabled,
                   maturity, diagnostics, discovered_at
            FROM plugin_registry
            ORDER BY plugin_id
        """),
    )).mappings().fetchall()

    return {
        "total": len(rows),
        "plugins": [
            {
                "plugin_id": r["plugin_id"],
                "version": r["version"],
                "name": r["name"],
                "author": r["author"],
                "status": r["status"],
                "enabled": r["enabled"],
                "maturity": r["maturity"],
                "signed": bool(r["diagnostics"] and r["diagnostics"].get("signature")),
                "discovered_at": str(r["discovered_at"]),
            }
            for r in rows
        ],
    }


@router.post("/api/v1/admin/plugins/{plugin_id}/quota")
async def set_plugin_quota(
    plugin_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
) -> dict:
    """Set per-plugin quota (max jobs per hour, per user)."""
    if not authorization or not _verify_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")

    max_jobs_per_hour = body.get("max_jobs_per_hour", 10)

    await db.execute(
        text("""
            UPDATE plugin_registry
            SET diagnostics = jsonb_set(
                COALESCE(diagnostics, '{}'::jsonb),
                '{quota}',
                :quota::jsonb
            )
            WHERE plugin_id = :pid
        """),
        {"pid": plugin_id, "quota": json.dumps({"max_jobs_per_hour": max_jobs_per_hour})},
    )
    await db.commit()

    return {
        "plugin_id": plugin_id,
        "max_jobs_per_hour": max_jobs_per_hour,
    }


def _verify_admin(authorization: str) -> bool:
    """Check the Authorization header against the configured admin API key."""
    if not settings.admin.admin_api_key:
        return True  # No key configured = open
    return authorization == f"Bearer {settings.admin.admin_api_key}"
