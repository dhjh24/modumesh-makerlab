"""Opaque session tokens and HMAC-signed download URLs."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from uuid import UUID


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sign_download(
    *,
    secret: str,
    file_id: UUID | str,
    expires_at: int,
    user_id: UUID | str,
) -> str:
    payload = f"{file_id}:{expires_at}:{user_id}"
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_download_signature(
    *,
    secret: str,
    file_id: UUID | str,
    expires_at: int,
    user_id: UUID | str,
    signature: str,
) -> bool:
    if expires_at < int(time.time()):
        return False
    expected = sign_download(
        secret=secret,
        file_id=file_id,
        expires_at=expires_at,
        user_id=user_id,
    )
    return hmac.compare_digest(expected, signature)
