from unittest.mock import MagicMock

import pytest
from fastapi import Request

from core.auth_rate_limiter import RateLimitExceeded, check_login_rate_limit


def _request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_login_rate_limit_blocks_after_threshold(monkeypatch):
    redis = MagicMock()
    redis.pipeline.return_value = redis
    redis.execute.side_effect = [
        (0, True, 6, True),
    ]
    monkeypatch.setattr(
        "core.auth_rate_limiter.get_redis_connection", lambda: redis
    )
    monkeypatch.setattr(
        "core.auth_rate_limiter.settings.auth_login_rate_limit", 5
    )
    monkeypatch.setattr(
        "core.auth_rate_limiter.settings.auth_login_rate_window_seconds", 60
    )
    redis.zrange.return_value = [(b"1", 0.0)]

    with pytest.raises(RateLimitExceeded) as exc:
        check_login_rate_limit(_request())
    assert exc.value.status_code == 429
