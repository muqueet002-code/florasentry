"""Password hashing and JWT handling (TRD 13.1, 13.2).

IMPLEMENTATION DECISIONS (deviations from the TRD's library suggestions, with reasons):

1. `argon2-cffi` is used directly instead of `passlib[argon2]`.
   passlib 1.7.4 imports the stdlib `crypt` module, which was REMOVED in Python 3.13
   (PEP 594). It cannot run on the Python versions this project targets. argon2-cffi is
   the maintained reference binding and provides the same Argon2id algorithm the TRD
   specifies, so the security property is unchanged.

2. `PyJWT` is used instead of `python-jose`.
   PyJWT is actively maintained and is the more common FastAPI pairing. The token
   contents, algorithm (HS256) and lifetimes are exactly as specified in TRD 13.1.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings
from app.core.errors import TokenExpiredError, ValidationError

TokenType = Literal["access", "refresh"]

_hasher = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
)

# A valid Argon2 hash of a random value, used to keep login timing constant when the
# user does not exist (TRD 13.2: no user-existence disclosure).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


# ---- Passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    validate_password_strength(password)
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a password. Always performs a hash comparison, even for a missing user."""
    target = password_hash or _DUMMY_HASH
    try:
        _hasher.verify(target, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    return password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    """True when the hash was produced with weaker parameters than currently configured."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def validate_password_strength(password: str) -> None:
    """Deliberately light (TRD 13.2): the primary users are farmers on basic phones.

    The tradeoff is stated in the TRD rather than hidden.
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValidationError(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.",
            message_key="errors.password_too_short",
            details=[{"field": "password", "issue": "too_short"}],
        )
    if password.lower() in _COMMON_PASSWORDS:
        raise ValidationError(
            "This password is too common.",
            message_key="errors.password_too_common",
            details=[{"field": "password", "issue": "too_common"}],
        )


# Small bundled list, per TRD 13.2. Not a substitute for a breach corpus.
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty123",
        "abc12345",
        "11111111",
        "iloveyou",
        "admin123",
        "welcome1",
        "letmein1",
        "florasentry",
        "changeme",
        "passw0rd",
    }
)


# ---- JWT access tokens -------------------------------------------------------


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: str,
    farmer_id: uuid.UUID | None = None,
    district_code: str | None = None,
) -> tuple[str, int]:
    """Return (token, expires_in_seconds). Claims per TRD 13.1."""
    now = datetime.now(UTC)
    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TTL_MIN)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if farmer_id:
        payload["farmer_id"] = str(farmer_id)
    if district_code:
        payload["district_code"] = district_code
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token, or raise an authentication error."""
    from app.core.errors import AuthenticationError

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(
            "Invalid token.", code="AUTH_INVALID_TOKEN", message_key="errors.auth_invalid_token"
        ) from exc
    if payload.get("type") != "access":
        raise AuthenticationError(
            "Wrong token type.", code="AUTH_INVALID_TOKEN", message_key="errors.auth_invalid_token"
        )
    return payload


# ---- Refresh tokens ----------------------------------------------------------
# Opaque random strings; only the SHA-256 hash is stored (TRD 13.1).


def generate_refresh_token() -> tuple[str, str]:
    """Return (plaintext_token, sha256_hash)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)
