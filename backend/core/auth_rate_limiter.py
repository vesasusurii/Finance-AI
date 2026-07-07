"""Redis sliding-window rate limits for authentication endpoints."""

from __future__ import annotations

import time

from fastapi import HTTPException, Request
from redis.exceptions import RedisError

from config import settings
from core.debug_logger import get_logger
from core.redis_client import get_redis_connection

logger = get_logger(__name__)


class RateLimitExceeded(HTTPException):
    def __init__(self, *, retry_after_seconds: int, message: str) -> None:
        super().__init__(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": message,
                "retry_after_seconds": retry_after_seconds,
            },
        )
        self.retry_after_seconds = retry_after_seconds


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_rate_limit(*, key: str, limit: int, window_seconds: int) -> None:
    if limit <= 0:
        return
    try:
        redis = get_redis_connection()
        now = time.time()
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 1)
        _, _, count, _ = pipe.execute()
    except RedisError:
        logger.warning("Redis unavailable for rate limit key=%s; allowing request", key)
        return
    if int(count) > limit:
        oldest = redis.zrange(key, 0, 0, withscores=True)
        retry_after = window_seconds
        if oldest:
            retry_after = max(1, int(window_seconds - (now - oldest[0][1])))
        raise RateLimitExceeded(
            retry_after_seconds=retry_after,
            message="Too many requests. Please try again later.",
        )


def check_login_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    _check_rate_limit(
        key=f"ratelimit:login:{ip}",
        limit=settings.auth_login_rate_limit,
        window_seconds=settings.auth_login_rate_window_seconds,
    )


def check_forgot_password_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    _check_rate_limit(
        key=f"ratelimit:forgot-password:{ip}",
        limit=settings.auth_forgot_password_rate_limit,
        window_seconds=settings.auth_forgot_password_rate_window_seconds,
    )
