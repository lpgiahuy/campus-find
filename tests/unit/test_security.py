import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    hashed = hash_password("matkhau123")
    assert verify_password("matkhau123", hashed)
    assert not verify_password("sai-mat-khau", hashed)


def test_verify_password_accepts_seed_hash():
    # scripts/seed_demo.py băm mật khẩu admin theo cách này
    seed_hash = PasswordHash.recommended().hash("admin-password-123")
    assert verify_password("admin-password-123", seed_hash)


def test_access_token_roundtrip():
    user_id = uuid.uuid4()
    payload = decode_token(create_access_token(user_id, "USER"))
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "USER"


def test_decode_token_rejects_wrong_signature():
    token = jwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "another-secret-key-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        decode_token(token)


def test_decode_token_rejects_expired_token():
    token = jwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        decode_token(token)


def test_decode_token_rejects_garbage():
    with pytest.raises(UnauthorizedError):
        decode_token("not-a-jwt")
