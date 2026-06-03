from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from core.debug_logger import get_logger
from core.redis_client import get_redis_connection

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class RedisCache:
    def get_model(self, key: str, model: type[T]) -> T | None:
        try:
            raw = get_redis_connection().get(key)
            if not raw:
                return None
            return model.model_validate_json(raw)
        except Exception:
            logger.exception("Redis cache read failed key=%s", key)
            return None

    def set_model(self, key: str, value: BaseModel, *, ttl_seconds: int) -> None:
        try:
            get_redis_connection().setex(
                key,
                ttl_seconds,
                value.model_dump_json(),
            )
        except Exception:
            logger.exception("Redis cache write failed key=%s", key)

    def set_json(self, key: str, value: dict, *, ttl_seconds: int) -> None:
        try:
            get_redis_connection().setex(key, ttl_seconds, json.dumps(value))
        except Exception:
            logger.exception("Redis cache JSON write failed key=%s", key)

    def delete_pattern(self, pattern: str) -> None:
        try:
            redis = get_redis_connection()
            for key in redis.scan_iter(match=pattern, count=200):
                redis.delete(key)
        except Exception:
            logger.exception("Redis cache invalidation failed pattern=%s", pattern)


cache = RedisCache()
