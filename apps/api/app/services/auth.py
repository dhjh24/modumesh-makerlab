"""Authentication service — bootstrap, login, sessions, users."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Session, User
from app.security import (
    generate_session_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.services.audit import record_audit

DEFAULT_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


async def ensure_bootstrap_users(session: AsyncSession) -> User:
    """Ensure bootstrap admin exists with a usable password hash.

    The migration seeds username=admin / role=admin for DEFAULT_OWNER_ID.
    Password is applied from API_BOOTSTRAP_ADMIN_PASSWORD on first start.
    """
    user = await session.get(User, DEFAULT_OWNER_ID)
    if user is None:
        user = User(
            id=DEFAULT_OWNER_ID,
            external_id="local-default",
            display_name="Administrator",
            username=settings.api.bootstrap_admin_username,
            role="admin",
            is_active=True,
            password_hash=hash_password(settings.api.bootstrap_admin_password),
        )
        session.add(user)
        await session.flush()
        return user

    changed = False
    if not user.username:
        user.username = settings.api.bootstrap_admin_username
        changed = True
    if user.role != "admin":
        user.role = "admin"
        changed = True
    if not user.password_hash:
        user.password_hash = hash_password(settings.api.bootstrap_admin_password)
        changed = True
    if changed:
        user.updated_at = datetime.now(timezone.utc)
        await session.flush()
    return user


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    display_name: str,
    role: str = "owner",
    actor: str = "system",
) -> User:
    existing = await session.execute(
        select(User).where(User.username == username)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Username '{username}' already exists")
    if role not in ("owner", "admin"):
        raise ValueError("role must be 'owner' or 'admin'")
    user = User(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        is_active=True,
        external_id=f"local:{username}",
    )
    session.add(user)
    await session.flush()
    await record_audit(
        session,
        entity_type="user",
        entity_id=user.id,
        action="user.created",
        actor=actor,
        details={"username": username, "role": role},
    )
    return user


async def authenticate(
    session: AsyncSession,
    *,
    username: str,
    password: str,
) -> Optional[User]:
    await ensure_bootstrap_users(session)
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    return user


async def create_session(
    session: AsyncSession,
    *,
    user: User,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> tuple[Session, str]:
    raw = generate_session_token()
    expires = datetime.now(timezone.utc) + timedelta(
        hours=settings.api.session_ttl_hours
    )
    row = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=expires,
        user_agent=(user_agent or "")[:512] or None,
        ip_address=(ip_address or "")[:64] or None,
        last_seen_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()
    await record_audit(
        session,
        entity_type="user",
        entity_id=user.id,
        action="user.login",
        actor=user.username or str(user.id),
        details={"session_id": str(row.id)},
    )
    return row, raw


async def get_valid_session(
    session: AsyncSession, raw_token: str
) -> Optional[Session]:
    if not raw_token:
        return None
    digest = hash_token(raw_token)
    result = await session.execute(
        select(Session).where(Session.token_hash == digest)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    now = datetime.now(timezone.utc)
    if row.revoked_at is not None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return None
    return row


async def touch_session(session: AsyncSession, row: Session) -> None:
    row.last_seen_at = datetime.now(timezone.utc)
    await session.flush()


async def revoke_session(
    session: AsyncSession,
    row: Session,
    *,
    actor: str,
) -> None:
    row.revoked_at = datetime.now(timezone.utc)
    await session.flush()
    await record_audit(
        session,
        entity_type="user",
        entity_id=row.user_id,
        action="user.logout",
        actor=actor,
        details={"session_id": str(row.id)},
    )


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at.asc()))
    return list(result.scalars().all())
