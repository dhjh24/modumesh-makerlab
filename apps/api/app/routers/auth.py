"""Authentication routes — register, login, logout, me (GM-10).

Register/login are deliberately rate-limited harder than the default
(5/min per IP — see ``RateLimitMiddleware`` auth overrides) because they are
the credential brute-force surface.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security.auth import require_user
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create an account and return a bearer token for it."""
    email = body.email.strip().lower()
    if not auth_service.is_valid_email(email):
        raise HTTPException(status_code=422, detail="Invalid email format")
    if await auth_service.get_user_by_email(db, email) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await auth_service.create_user(
        db,
        email=email,
        password=body.password,
        display_name=body.display_name,
    )
    token, raw = await auth_service.issue_token(db, user)
    await db.commit()
    return TokenResponse(
        access_token=raw,
        expires_at=token.expires_at,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange credentials for a bearer token.

    Unknown email and wrong password produce the identical 401 response so
    the endpoint cannot be used for account enumeration.
    """
    user = await auth_service.authenticate(
        db, email=body.email, password=body.password
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token, raw = await auth_service.issue_token(db, user)
    await db.commit()
    return TokenResponse(
        access_token=raw,
        expires_at=token.expires_at,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=204)
async def logout(
    authorization: Optional[str] = Header(default=None),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the presented token. Idempotent; always 204 when authenticated."""
    if authorization and authorization.lower().startswith("bearer "):
        await auth_service.revoke_token(db, authorization[7:].strip())
    return None


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(require_user)) -> UserOut:
    """Return the authenticated user's public profile."""
    return UserOut.model_validate(current_user)
