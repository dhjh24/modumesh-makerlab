"""Authentication and authorization dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Project, User
from app.services import auth as auth_service


@dataclass(frozen=True)
class AuthContext:
    user: User
    session_id: UUID
    token: str

    @property
    def is_admin(self) -> bool:
        return self.user.role == "admin"

    @property
    def actor(self) -> str:
        return self.user.username or str(self.user.id)


async def _resolve_token(
    request: Request,
    authorization: Optional[str],
    session_cookie: Optional[str],
) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    if session_cookie:
        return session_cookie.strip() or None
    # Dev/test escape hatch: X-API-Token header mirrors bootstrap admin when set.
    api_token = request.headers.get("X-API-Token")
    if api_token:
        return api_token.strip() or None
    return None


async def get_optional_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
    modumesh_session: Optional[str] = Cookie(default=None, alias="modumesh_session"),
) -> Optional[AuthContext]:
    if not settings.api.auth_enabled:
        user = await auth_service.ensure_bootstrap_users(db)
        return AuthContext(user=user, session_id=user.id, token="")

    token = await _resolve_token(request, authorization, modumesh_session)
    if not token:
        return None
    session = await auth_service.get_valid_session(db, token)
    if session is None:
        return None
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    await auth_service.touch_session(db, session)
    return AuthContext(user=user, session_id=session.id, token=token)


async def require_auth(
    auth: Optional[AuthContext] = Depends(get_optional_auth),
) -> AuthContext:
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth


async def require_admin(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    if not auth.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
    return auth


def assert_project_access(auth: AuthContext, project: Project) -> None:
    """Owner or admin may access a project. Raise 403 otherwise."""
    if auth.is_admin:
        return
    if project.owner_id != auth.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this project",
        )
