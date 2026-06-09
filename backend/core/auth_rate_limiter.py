"""Redis sliding-window rate limits for authentication endpoints."""

from __future__ import annotations

import time

from fastapi import HTTPException, Request

from config import settings
from core.redis_client import get_redis_connection


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
    redis = get_redis_connection()
    now = time.time()
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_seconds)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds + 1)
    _, _, count, _ = pipe.execute()
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


def check_verify_rate_limit(user_id: int) -> None:
    _check_rate_limit(
        key=f"ratelimit:verify:{user_id}",
        limit=settings.auth_verify_rate_limit,
        window_seconds=settings.auth_verify_rate_window_seconds,
    )


def check_resend_ip_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    _check_rate_limit(
        key=f"ratelimit:resend:{ip}",
        limit=settings.auth_resend_ip_rate_limit,
        window_seconds=settings.auth_resend_ip_rate_window_seconds,
    )


def check_verification_attempts(user_id: int) -> None:
    redis = get_redis_connection()
    key = f"verify:attempts:{user_id}"
    attempts = int(redis.get(key) or 0)
    if attempts >= settings.auth_verify_max_attempts:
        ttl = redis.ttl(key)
        retry = max(1, int(ttl)) if ttl and ttl > 0 else 60
        raise RateLimitExceeded(
            retry_after_seconds=retry,
            message="Too many failed verification attempts. Request a new code.",
        )


def record_verification_failure(user_id: int) -> None:
    redis = get_redis_connection()
    key = f"verify:attempts:{user_id}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, settings.auth_verify_rate_window_seconds)
    pipe.execute()


def clear_verification_attempts(user_id: int) -> None:
    get_redis_connection().delete(f"verify:attempts:{user_id}")
