"""Password hashing and session tokens.

`hashlib.scrypt` rather than bcrypt or argon2: it is memory-hard, in the standard
library, and needs no dependency to audit. The parameters below target roughly
100ms per verification on ordinary hardware, which is the point — a hash that is
fast to check is fast to attack.

Hashes are self-describing (`scrypt$n$r$p$salt$key`), so the cost parameters can
be raised later without invalidating existing passwords: an old hash still says
how it was made.
"""

from __future__ import annotations

import base64
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings

# ~100ms and 16MB per verification. Raise N as hardware improves; stored hashes
# carry their own parameters, so old passwords keep working.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DK_LEN = 32

JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=14)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = _derive(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check against a stored hash, using that hash's own parameters."""
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(key_b64)
        actual = _derive(password, _unb64(salt_b64), int(n), int(r), int(p), len(expected))
    except (ValueError, TypeError):
        # A malformed hash is a failed login, never a 500.
        return False
    # compare_digest, not ==, so a wrong password cannot be found byte by byte.
    return hmac.compare_digest(expected, actual)


def _derive(
    password: str, salt: bytes, n: int, r: int, p: int, dklen: int = _DK_LEN
) -> bytes:
    import hashlib

    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen,
        maxmem=132 * 1024 * 1024,
    )


def issue_token(*, user_id: str, business_id: str, role: str, email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "biz": business_id,
            "role": role,
            "email": email,
            "iat": now,
            "exp": now + TOKEN_TTL,
        },
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )


def read_token(token: str) -> dict[str, Any] | None:
    """Decode a session token, or None if it is invalid, expired or not ours."""
    try:
        return jwt.decode(
            token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None


# Verified against when no account exists, so a missing email costs the same as a
# wrong password. Computed once, lazily — hashing on import would slow startup
# for something most requests never touch.
_DUMMY: str | None = None


def dummy_hash() -> str:
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password(secrets.token_urlsafe(32))
    return _DUMMY
