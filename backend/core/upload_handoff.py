from __future__ import annotations

from redis.exceptions import RedisError

from core.debug_logger import get_logger
from core.redis_client import get_redis_connection

logger = get_logger(__name__)

_KEY_PREFIX = "upload:bytes:"
_TTL_SECONDS = 10 * 60


def _key(upload_id: int) -> str:
    return f"{_KEY_PREFIX}{upload_id}"


def store_upload_bytes(upload_id: int, content: bytes | None) -> None:
    if not content:
        return
    try:
        get_redis_connection().set(_key(upload_id), content, ex=_TTL_SECONDS)
    except RedisError as exc:
        logger.debug("Upload byte handoff skipped for upload_id=%d: %s", upload_id, exc)


def pop_upload_bytes(upload_id: int) -> bytes | None:
    try:
        redis = get_redis_connection()
        key = _key(upload_id)
        data = redis.get(key)
        if data is not None:
            redis.delete(key)
        return data
    except RedisError as exc:
        logger.debug("Upload byte handoff read skipped for upload_id=%d: %s", upload_id, exc)
        return None
