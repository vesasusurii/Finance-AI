"""Server-side refresh token jti tracking for rotation and logout."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from redis.exceptions import RedisError

from config import settings
from core.debug_logger import get_logger
from core.redis_client import get_redis_connection

logger = get_logger(__name__)

_REFRESH_PREFIX = "refresh:"


def _redis_required() -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "service_unavailable",
            "message": "Authentication service is temporarily unavailable. Please try again shortly.",
        },
    )


def _ttl_seconds() -> int:
    return settings.jwt_refresh_expire_days * 24 * 60 * 60


def new_refresh_jti() -> str:
    return str(uuid.uuid4())


def store_refresh_jti(user_id: int, jti: str) -> None:
    key = f"{_REFRESH_PREFIX}{user_id}:{jti}"
    try:
        get_redis_connection().setex(key, _ttl_seconds(), b"1")
    except RedisError:
        logger.exception("Redis unavailable while storing refresh token for user_id=%d", user_id)
        _redis_required()


def consume_refresh_jti(user_id: int, jti: str) -> bool:
    """Validate and delete a refresh jti (one-time use on rotation)."""
    if not jti:
        return False
    try:
        redis = get_redis_connection()
        key = f"{_REFRESH_PREFIX}{user_id}:{jti}"
        deleted = redis.delete(key)
        return bool(deleted)
    except RedisError:
        logger.exception("Redis unavailable while consuming refresh token for user_id=%d", user_id)
        _redis_required()
        return False


def revoke_all_refresh_tokens(user_id: int) -> None:
    try:
        redis = get_redis_connection()
        pattern = f"{_REFRESH_PREFIX}{user_id}:*"
        for key in redis.scan_iter(match=pattern, count=200):
            redis.delete(key)
    except RedisError:
        logger.exception("Redis unavailable while revoking refresh tokens for user_id=%d", user_id)
        _redis_required()
