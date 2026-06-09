"""Server-side refresh token jti tracking for rotation and logout."""

from __future__ import annotations

import uuid

from config import settings
from core.redis_client import get_redis_connection

_REFRESH_PREFIX = "refresh:"


def _ttl_seconds() -> int:
    return settings.jwt_refresh_expire_days * 24 * 60 * 60


def new_refresh_jti() -> str:
    return str(uuid.uuid4())


def store_refresh_jti(user_id: int, jti: str) -> None:
    key = f"{_REFRESH_PREFIX}{user_id}:{jti}"
    get_redis_connection().setex(key, _ttl_seconds(), b"1")


def consume_refresh_jti(user_id: int, jti: str) -> bool:
    """Validate and delete a refresh jti (one-time use on rotation)."""
    if not jti:
        return False
    redis = get_redis_connection()
    key = f"{_REFRESH_PREFIX}{user_id}:{jti}"
    deleted = redis.delete(key)
    return bool(deleted)


def revoke_all_refresh_tokens(user_id: int) -> None:
    redis = get_redis_connection()
    pattern = f"{_REFRESH_PREFIX}{user_id}:*"
    for key in redis.scan_iter(match=pattern, count=200):
        redis.delete(key)
