from __future__ import annotations

from core.redis_client import get_redis_connection


def acquire_lock(key: str, owner: str, *, ttl_seconds: int) -> bool:
    return bool(get_redis_connection().set(key, owner, nx=True, ex=ttl_seconds))


def acquire_ocr_lock(upload_id: int, owner: str) -> str | None:
    key = f"lock:ocr:{upload_id}"
    return key if acquire_lock(key, owner, ttl_seconds=30 * 60) else None


def acquire_review_lock(task_id: int, owner: str) -> str | None:
    key = f"lock:review:{task_id}"
    return key if acquire_lock(key, owner, ttl_seconds=10 * 60) else None


def acquire_transaction_lock(scope_id: int, owner: str) -> str | None:
    """Scope is bank_statement_id, or 0 for a global reconciliation run."""
    key = f"lock:transaction:{scope_id}"
    return key if acquire_lock(key, owner, ttl_seconds=60 * 60) else None


def release_lock(key: str | None, owner: str) -> None:
    if key is None:
        return
    redis = get_redis_connection()
    value = redis.get(key)
    if value is None:
        return
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if value == owner:
        redis.delete(key)
