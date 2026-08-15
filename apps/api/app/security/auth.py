"""Bearer-token authentication dependency (GM-10).

``require_user`` reads ``Authorization: Bearer <token>``, resolves it against
the ``auth_tokens`` table (sha256 digest lookup, expired/revoked tokens are
rejected) and returns the owning :class:`~app.models.User`. Every per-user
route depends on it; unauthenticated requests get a 401.

Admin gating stays in :mod:`app.security.admin` (fail-closed API key) and is
independent of user auth.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.services.auth import get_user_by_token


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Extract the raw token from an Authorization header, or None."""
    if not authorization:
        return None
    scheme, _, rest = authorization.partition(" ")
    if scheme.lower() != "bearer" or not rest.strip():
        return None
    return rest.strip()


async def require_user(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: 401 unless a valid bearer token is presented.

    Use as ``current_user: User = Depends(require_user)``.
    """
    raw = _bearer_token(authorization)
    if raw is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_user_by_token(db, raw)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# Alias for readability on routes that read the current user without
# implying anything about admin privileges.
get_current_user = require_user
