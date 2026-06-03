from __future__ import annotations

import json
import time

from openai import APIConnectionError, APIStatusError, RateLimitError
from sqlalchemy.exc import SQLAlchemyError

from core.redis_client import get_redis_connection
from core.worker_exceptions import RateLimitExceeded
from core.worker_metrics import metrics_snapshot


def classify_failure(exc: Exception) -> str:
    text = str(exc).lower()
    if isinstance(exc, (RateLimitExceeded, RateLimitError)) or "rate limit" in text:
        return "rate_limit"
    if "password-protected pdf" in text or "invalid pdf" in text:
        return "invalid_pdf"
    if isinstance(exc, SQLAlchemyError) or "database" in text or "db" in text:
        return "db_error"
    if isinstance(exc, (TimeoutError, APIConnectionError)) or "timeout" in text:
        return "timeout"
    if isinstance(exc, APIStatusError) or "openai" in text:
        return "openai_failure"
    return "unknown"


def record_dlq_entry(
    *,
    task_name: str,
    args: dict,
    exc: Exception,
    retry_history: list[dict] | None = None,
) -> None:
    entry = {
        "task_name": task_name,
        "args": args,
        "failure_category": classify_failure(exc),
        "failure_reason": str(exc),
        "retry_history": retry_history or [],
        "metrics": metrics_snapshot(),
        "created_at": time.time(),
    }
    get_redis_connection().lpush("dlq:tasks", json.dumps(entry, default=str))
