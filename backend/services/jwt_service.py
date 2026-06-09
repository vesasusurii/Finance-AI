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
    token_version: int = 1,
) -> str:
    exp = _now_utc() + timedelta(minutes=settings.jwt_access_expire_minutes)
    return _encode(
        {
            "user_id": user_id,
            "email": email,
            "role": role,
            "email_verified": email_verified,
            "must_change_password": must_change_password,
            "token_version": token_version,
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
    token_version: int = 1,
    jti: str,
) -> str:
    exp = _now_utc() + timedelta(days=settings.jwt_refresh_expire_days)
    return _encode(
        {
            "user_id": user_id,
            "email": email,
            "role": role,
            "email_verified": email_verified,
            "must_change_password": must_change_password,
            "token_version": token_version,
            "jti": jti,
            "type": TOKEN_TYPE_REFRESH,
            "exp": exp,
        }
    )


def _decode_payload(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


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


def get_access_token_version(token: str) -> int | None:
    payload = _decode_payload(token)
    if not payload or payload.get("type") != TOKEN_TYPE_ACCESS:
        return None
    try:
        return int(payload.get("token_version", 1))
    except (TypeError, ValueError):
        return None


def decode_refresh_token(token: str) -> tuple[UserContext | None, str | None]:
    payload = _decode_payload(token)
    if payload is None:
        return None, None
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        return None, None
    user = _payload_to_context(payload)
    if user is None:
        return None, None
    jti = str(payload.get("jti", ""))
    try:
        version = int(payload.get("token_version", 1))
    except (TypeError, ValueError):
        version = 1
    return user, jti if jti else None


def get_refresh_token_version(token: str) -> int | None:
    payload = _decode_payload(token)
    if not payload or payload.get("type") != TOKEN_TYPE_REFRESH:
        return None
    try:
        return int(payload.get("token_version", 1))
    except (TypeError, ValueError):
        return None


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
