"""Cache user.token_version in Redis to avoid per-request DB hits."""

from __future__ import annotations

from core.redis_client import get_redis_connection

_CACHE_TTL_SECONDS = 60
_KEY_PREFIX = "user:token_version:"


def cache_token_version(user_id: int, version: int) -> None:
    get_redis_connection().setex(
        f"{_KEY_PREFIX}{user_id}", _CACHE_TTL_SECONDS, str(version)
    )


def get_cached_token_version(user_id: int) -> int | None:
    raw = get_redis_connection().get(f"{_KEY_PREFIX}{user_id}")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def invalidate_token_version_cache(user_id: int) -> None:
    get_redis_connection().delete(f"{_KEY_PREFIX}{user_id}")
