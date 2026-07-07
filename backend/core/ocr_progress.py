from __future__ import annotations

import json
import time
from typing import Any

from redis.exceptions import RedisError

from core.debug_logger import get_logger
from core.redis_client import get_redis_connection

logger = get_logger(__name__)

_PROGRESS_PREFIX = "ocr:progress:"
_RECENT_KEY = "metrics:ocr:recent"
_PROGRESS_TTL_SECONDS = 30 * 60
_RECENT_TTL_SECONDS = 60 * 60
_RECENT_LIMIT = 50


def _progress_key(upload_id: int) -> str:
    return f"{_PROGRESS_PREFIX}{upload_id}"


def update_ocr_progress(upload_id: int, **fields: Any) -> None:
    payload = {
        key: json.dumps(value, default=str)
        for key, value in fields.items()
        if value is not None
    }
    if not payload:
        return
    payload["updated_at"] = json.dumps(time.time())
    try:
        redis = get_redis_connection()
        redis.hset(_progress_key(upload_id), mapping=payload)
        redis.expire(_progress_key(upload_id), _PROGRESS_TTL_SECONDS)
    except RedisError as exc:
        logger.debug("OCR progress update skipped for upload_id=%d: %s", upload_id, exc)


def get_ocr_progress(upload_id: int) -> dict[str, Any]:
    try:
        raw = get_redis_connection().hgetall(_progress_key(upload_id))
    except RedisError as exc:
        logger.debug("OCR progress read skipped for upload_id=%d: %s", upload_id, exc)
        return {}
    result: dict[str, Any] = {}
    for key, value in raw.items():
        name = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        text = value.decode("utf-8") if isinstance(value, bytes) else str(value)
        try:
            result[name] = json.loads(text)
        except json.JSONDecodeError:
            result[name] = text
    return result


def record_recent_ocr_timing(payload: dict[str, Any]) -> None:
    entry = {
        "recorded_at": time.time(),
        **payload,
    }
    try:
        redis = get_redis_connection()
        member = json.dumps(entry, default=str, sort_keys=True)
        redis.zadd(_RECENT_KEY, {member: entry["recorded_at"]})
        redis.zremrangebyrank(_RECENT_KEY, 0, -(_RECENT_LIMIT + 1))
        redis.expire(_RECENT_KEY, _RECENT_TTL_SECONDS)
    except RedisError as exc:
        logger.debug("Recent OCR timing update skipped: %s", exc)


def recent_ocr_timings(limit: int = 10) -> list[dict[str, Any]]:
    try:
        rows = get_redis_connection().zrevrange(_RECENT_KEY, 0, max(0, limit - 1))
    except RedisError as exc:
        logger.debug("Recent OCR timing read skipped: %s", exc)
        return []
    result: list[dict[str, Any]] = []
    for raw in rows:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        try:
            result.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return result
