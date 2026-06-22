"""Password hashing + JWT helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt operates on the first 72 bytes only; we truncate explicitly to avoid
# the ValueError newer bcrypt releases raise on longer inputs.
_BCRYPT_MAX_BYTES = 72


def _prepare(raw: str) -> bytes:
    return raw.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_prepare(raw), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(raw), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None


def create_signed_token(subject: str | int, purpose: str, minutes: int) -> str:
    """Mint a short-lived, purpose-scoped token (email verification, reset, ...)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(subject), "purpose": purpose, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_signed_token(token: str, purpose: str) -> str | None:
    """Return the subject if the token is valid AND matches the expected purpose."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("purpose") != purpose:
        return None
    return payload.get("sub")
