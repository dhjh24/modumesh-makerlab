"""Fail-closed admin authentication dependency.

Admin endpoints (plugin signing, quota, plugin enable/disable/resync) are
control-plane operations. They must never be reachable without a valid admin
API key — even when no key has been configured (fail closed, not open).
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import settings


def _admin_key_valid(authorization: str | None) -> bool:
    """Return True only when the header carries the configured admin key.

    Fail-closed: an unset ``ADMIN_API_KEY`` makes every request invalid, so a
    default deployment cannot be administered without explicitly configuring
    a key (the API also refuses to boot in that state — see ``main.lifespan``).
    """
    configured = settings.admin.admin_api_key
    if not configured:
        return False
    return authorization == f"Bearer {configured}"


async def require_admin(authorization: str | None = Header(None)) -> None:
    """FastAPI dependency: 403 unless a valid ``Authorization: Bearer <key>``.

    Use as ``admin: None = Depends(require_admin)`` on control-plane routes.
    """
    if not _admin_key_valid(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")
