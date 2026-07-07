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

# Scalar timing fields exposed on progress, status API, and recent_ocr_timings.
OCR_TIMING_SCALAR_FIELDS: tuple[str, ...] = (
    "queue_wait_ms",
    "storage_download_ms",
    "download_ms",
    "text_extraction_ms",
    "document_classification_ms",
    "text_llm_ms",
    "render_ms",
    "merge_ms",
    "hybrid_merge_ms",
    "field_recovery_ms",
    "validation_ms",
    "ocr_ms",
    "persist_ms",
    "openai_total_ms",
    "total_ms",
)


def normalize_ocr_timing_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure consistent timing keys for metrics and status consumers."""
    normalized = dict(payload)
    storage = normalized.get("storage_download_ms")
    download = normalized.get("download_ms")
    if storage is not None and download is None:
        normalized["download_ms"] = storage
    elif download is not None and storage is None:
        normalized["storage_download_ms"] = download
    for field in OCR_TIMING_SCALAR_FIELDS:
        normalized.setdefault(field, None)
    if normalized.get("openai_call_count") is None:
        calls = normalized.get("openai_calls")
        if isinstance(calls, list):
            normalized["openai_call_count"] = len(calls)
        else:
            normalized.setdefault("openai_call_count", None)
    normalized.setdefault("extraction_mode", None)
    return normalized


def _progress_key(upload_id: int) -> str:
    return f"{_PROGRESS_PREFIX}{upload_id}"


def update_ocr_progress(upload_id: int, **fields: Any) -> None:
    if any(key in OCR_TIMING_SCALAR_FIELDS for key in fields):
        fields = normalize_ocr_timing_fields(fields)
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
    if any(key in result for key in OCR_TIMING_SCALAR_FIELDS):
        return normalize_ocr_timing_fields(result)
    return result


def record_recent_ocr_timing(payload: dict[str, Any]) -> None:
    entry = normalize_ocr_timing_fields(
        {
            "recorded_at": time.time(),
            **payload,
        }
    )
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
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            result.append(normalize_ocr_timing_fields(parsed))
    return result


def openai_avg_from_recent_timings(limit: int = 20) -> float | None:
    """Mean OpenAI latency from recent production extractions (ms)."""
    values: list[float] = []
    for row in recent_ocr_timings(limit=limit):
        raw = row.get("openai_total_ms")
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return round(sum(values) / len(values), 1)
