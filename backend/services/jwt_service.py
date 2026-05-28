"""JWT access and refresh token helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from config import settings
from core.roles import ROLE_FINANCE, is_valid_role
from schemas.auth import UserContext

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_access_token(
    *,
    user_id: int,
    email: str,
    role: str,
    email_verified: bool = True,
    must_change_password: bool = False,
) -> str:
    exp = _now_utc() + timedelta(minutes=settings.jwt_access_expire_minutes)
    return _encode(
        {
            "user_id": user_id,
            "email": email,
            "role": role,
            "email_verified": email_verified,
            "must_change_password": must_change_password,
            "type": TOKEN_TYPE_ACCESS,
            "exp": exp,
        }
    )


def create_refresh_token(
    *,
    user_id: int,
    email: str,
    role: str,
    email_verified: bool = True,
    must_change_password: bool = False,
) -> str:
    exp = _now_utc() + timedelta(days=settings.jwt_refresh_expire_days)
    return _encode(
        {
            "user_id": user_id,
            "email": email,
            "role": role,
            "email_verified": email_verified,
            "must_change_password": must_change_password,
            "type": TOKEN_TYPE_REFRESH,
            "exp": exp,
        }
    )


def decode_access_token(token: str) -> tuple[UserContext | None, str | None]:
    """Return (user, error_code). error_code: token_expired | invalid_token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None, "token_expired"
    except jwt.PyJWTError:
        return None, "invalid_token"
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        return None, "invalid_token"
    user = _payload_to_context(payload)
    if user is None:
        return None, "invalid_token"
    return user, None


def decode_refresh_token(token: str) -> UserContext | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        return None
    return _payload_to_context(payload)


def _payload_to_context(payload: dict[str, Any]) -> UserContext | None:
    try:
        role = str(payload.get("role", ROLE_FINANCE))
        if not is_valid_role(role):
            role = ROLE_FINANCE
        return UserContext(
            user_id=int(payload["user_id"]),
            email=str(payload.get("email", "")),
            role=role,
            email_verified=bool(payload.get("email_verified", True)),
            must_change_password=bool(payload.get("must_change_password", False)),
        )
    except (KeyError, TypeError, ValueError):
        return None
