from __future__ import annotations

import random


def adaptive_backoff_seconds(
    attempt: int,
    *,
    base_seconds: float = 5.0,
    openai_rate_limited: bool = False,
    db_latency_high: bool = False,
    jitter_ratio: float = 0.2,
) -> int:
    delay = base_seconds * (2 ** max(0, attempt))
    if openai_rate_limited:
        delay *= 3
    if db_latency_high:
        delay *= 2
    jitter = delay * jitter_ratio
    return max(1, int(delay + random.uniform(-jitter, jitter)))
