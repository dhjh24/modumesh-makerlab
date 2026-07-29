"""Auth API routes — login, logout, me, admin user create."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import AuthContext, require_admin, require_auth
from app.schemas import (
    LoginRequest,
    LoginResponse,
    UserCreate,
    UserOut,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="modumesh_session",
        value=token,
        httponly=True,
        secure=settings.api.session_cookie_secure,
        samesite=settings.api.session_cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.api.session_ttl_hours * 3600,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    user = await auth_service.authenticate(
        db, username=body.username, password=body.password
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    client = request.client.host if request.client else None
    session_row, token = await auth_service.create_session(
        db,
        user=user,
        user_agent=request.headers.get("user-agent"),
        ip_address=client,
    )
    _set_session_cookie(response, token)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=session_row.expires_at,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if auth.token:
        row = await auth_service.get_valid_session(db, auth.token)
        if row is not None:
            await auth_service.revoke_session(db, row, actor=auth.actor)
    response.delete_cookie("modumesh_session", path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
async def me(auth: AuthContext = Depends(require_auth)) -> UserOut:
    return UserOut.model_validate(auth.user)


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    try:
        user = await auth_service.create_user(
            db,
            username=body.username,
            password=body.password,
            display_name=body.display_name,
            role=body.role,
            actor=auth.actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserOut.model_validate(user)


@router.get("/users", response_model=list[UserOut])
async def list_users(
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    users = await auth_service.list_users(db)
    return [UserOut.model_validate(u) for u in users]
