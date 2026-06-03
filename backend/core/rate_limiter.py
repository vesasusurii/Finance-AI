from __future__ import annotations

import time

from config import settings
from core.adaptive_backoff import adaptive_backoff_seconds
from core.redis_client import get_redis_connection
from core.worker_exceptions import RateLimitExceeded


def _token_bucket_key(model: str) -> str:
    return f"rate:openai:rps:{model}"


def _concurrency_key(model: str) -> str:
    return f"rate:openai:concurrency:{model}"


class OpenAIRateLease:
    def __init__(self, model: str) -> None:
        self.model = model
        self._acquired = False

    def __enter__(self) -> "OpenAIRateLease":
        if settings.queue_mode != "adaptive":
            self._acquired = True
            return self
        redis = get_redis_connection()
        now = time.time()
        window_key = _token_bucket_key(self.model)
        pipe = redis.pipeline()
        pipe.zremrangebyscore(window_key, 0, now - 1)
        pipe.zcard(window_key)
        _, count = pipe.execute()
        if int(count) >= settings.openai_rps_limit:
            raise RateLimitExceeded(
                "OpenAI RPS limit reached",
                retry_after_seconds=adaptive_backoff_seconds(
                    0, openai_rate_limited=True
                ),
            )
        redis.zadd(window_key, {str(now): now})
        redis.expire(window_key, 5)

        concurrent = redis.incr(_concurrency_key(self.model))
        redis.expire(_concurrency_key(self.model), 60)
        if int(concurrent) > settings.openai_concurrency_limit:
            redis.decr(_concurrency_key(self.model))
            raise RateLimitExceeded(
                "OpenAI concurrency limit reached",
                retry_after_seconds=adaptive_backoff_seconds(
                    0, openai_rate_limited=True
                ),
            )
        self._acquired = True
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        if self._acquired and settings.queue_mode == "adaptive":
            get_redis_connection().decr(_concurrency_key(self.model))
