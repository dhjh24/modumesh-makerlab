"""Phase 6 unit tests — tokens, passwords, rate-limit helpers."""

from __future__ import annotations

import time
from uuid import uuid4

from app.security.passwords import hash_password, verify_password
from app.security.tokens import (
    generate_session_token,
    hash_token,
    sign_download,
    verify_download_signature,
)


class TestPasswords:
    def test_hash_and_verify(self) -> None:
        h = hash_password("secret-password")
        assert h != "secret-password"
        assert verify_password("secret-password", h)
        assert not verify_password("wrong", h)


class TestTokens:
    def test_session_token_hash(self) -> None:
        t = generate_session_token()
        assert len(t) > 20
        assert hash_token(t) != t
        assert hash_token(t) == hash_token(t)

    def test_download_signature_roundtrip(self) -> None:
        secret = "test-secret"
        file_id = uuid4()
        user_id = uuid4()
        expires = int(time.time()) + 60
        sig = sign_download(
            secret=secret, file_id=file_id, expires_at=expires, user_id=user_id
        )
        assert verify_download_signature(
            secret=secret,
            file_id=file_id,
            expires_at=expires,
            user_id=user_id,
            signature=sig,
        )
        assert not verify_download_signature(
            secret=secret,
            file_id=file_id,
            expires_at=expires,
            user_id=user_id,
            signature="deadbeef",
        )

    def test_download_signature_expired(self) -> None:
        secret = "test-secret"
        file_id = uuid4()
        user_id = uuid4()
        expires = int(time.time()) - 10
        sig = sign_download(
            secret=secret, file_id=file_id, expires_at=expires, user_id=user_id
        )
        assert not verify_download_signature(
            secret=secret,
            file_id=file_id,
            expires_at=expires,
            user_id=user_id,
            signature=sig,
        )
