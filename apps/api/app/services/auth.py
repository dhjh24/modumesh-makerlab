"""Auth service — password hashing and opaque bearer tokens (stdlib only).

No JWT, no passlib/bcrypt. Passwords are hashed with PBKDF2-HMAC-SHA256
(per-user random 16-byte salt, stored as ``pbkdf2_sha256$<iter>$<salt_hex>$<hash_hex>``)
and compared with :func:`hmac.compare_digest`. Tokens are 256-bit random
opaque strings (``secrets.token_urlsafe(32)``); only their SHA-256 hex digest
is ever stored in the database, so a database leak cannot be replayed as
credentials.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuthToken, User

# Module constant so tests can lower it for speed; format embeds the actual
# iteration count, so verify_password stays correct across values.
PBKDF2_ITERATIONS = 600_000

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Passwords ──────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a per-user random salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of a password against a stored hash."""
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# ── Tokens ─────────────────────────────────────────────────────────────


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest of a raw token — the only form stored in the DB."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_token(
    user_id: uuid.UUID, ttl_hours: int | None = None
) -> tuple[str, datetime]:
    """Generate a raw opaque token and its expiry.

    Returns ``(raw_token, expires_at)``. The raw token is returned exactly
    once here and must never be persisted — store ``hash_token(raw_token)``.
    """
    raw = secrets.token_urlsafe(32)
    ttl = settings.api.token_ttl_hours if ttl_hours is None else ttl_hours
    expires_at = _utcnow() + timedelta(hours=ttl)
    return raw, expires_at


def is_valid_email(email: str) -> bool:
    """Cheap structural email check (no external validator dependency)."""
    return bool(_EMAIL_RE.match(email or ""))


# ── DB operations ──────────────────────────────────────────────────────


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    normalized = (email or "").strip().lower()
    return (
        await session.execute(
            select(User).where(User.email == normalized)
        )
    ).scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: Optional[str] = None,
) -> User:
    """Create a user with a hashed password (email already validated/normalized)."""
    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        display_name=(display_name or "").strip() or email.split("@")[0],
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate(
    session: AsyncSession, *, email: str, password: str
) -> Optional[User]:
    """Return the user when credentials are valid, else None.

    Unknown email and wrong password deliberately take the same code path so
    the response is identical (no account enumeration).
    """
    user = await get_user_by_email(session, email)
    if user is None or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def issue_token(
    session: AsyncSession, user: User, *, ttl_hours: int | None = None
) -> tuple[AuthToken, str]:
    """Persist a new token row (hash only) and return (row, raw_token)."""
    raw, expires_at = create_token(user.id, ttl_hours=ttl_hours)
    token = AuthToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=expires_at,
    )
    session.add(token)
    await session.flush()
    return token, raw


async def get_user_by_token(session: AsyncSession, raw_token: str) -> Optional[User]:
    """Resolve a raw token to its user, or None when invalid/expired/revoked.

    Touches ``last_used_at`` on the token row (fire-and-forget: the session
    commit at request end persists it; a failed request rolls it back).
    """
    token_hash = hash_token(raw_token)
    now = _utcnow()
    row = (
        await session.execute(
            select(AuthToken, User)
            .join(User, User.id == AuthToken.user_id)
            .where(
                AuthToken.token_hash == token_hash,
                AuthToken.revoked_at.is_(None),
                AuthToken.expires_at > now,
            )
        )
    ).first()
    if row is None:
        return None
    token, user = row
    token.last_used_at = now
    return user


async def revoke_token(session: AsyncSession, raw_token: str) -> bool:
    """Revoke a token by its raw value. Returns True when a row was revoked."""
    token = (
        await session.execute(
            select(AuthToken).where(AuthToken.token_hash == hash_token(raw_token))
        )
    ).scalar_one_or_none()
    if token is None or token.revoked_at is not None:
        return False
    token.revoked_at = _utcnow()
    await session.flush()
    return True
