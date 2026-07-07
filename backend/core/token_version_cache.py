"""Cache user.token_version in Redis to avoid per-request DB hits."""

from __future__ import annotations

from redis.exceptions import RedisError

from core.debug_logger import get_logger
from core.redis_client import get_redis_connection

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 60
_KEY_PREFIX = "user:token_version:"


def cache_token_version(user_id: int, version: int) -> None:
    try:
        get_redis_connection().setex(
            f"{_KEY_PREFIX}{user_id}", _CACHE_TTL_SECONDS, str(version)
        )
    except RedisError:
        logger.warning("Redis unavailable while caching token_version for user_id=%d", user_id)


def get_cached_token_version(user_id: int) -> int | None:
    try:
        raw = get_redis_connection().get(f"{_KEY_PREFIX}{user_id}")
    except RedisError:
        logger.warning("Redis unavailable while reading token_version for user_id=%d", user_id)
        return None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def invalidate_token_version_cache(user_id: int) -> None:
    try:
        get_redis_connection().delete(f"{_KEY_PREFIX}{user_id}")
    except RedisError:
        logger.warning(
            "Redis unavailable while invalidating token_version for user_id=%d",
            user_id,
        )
