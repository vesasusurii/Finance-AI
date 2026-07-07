from __future__ import annotations

from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from config import settings
from core.debug_logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=False)


def redis_ping() -> bool:
    try:
        return bool(get_redis_connection().ping())
    except RedisError:
        return False
