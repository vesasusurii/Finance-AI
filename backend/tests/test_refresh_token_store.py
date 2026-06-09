from unittest.mock import MagicMock

from services.refresh_token_store import (
    consume_refresh_jti,
    new_refresh_jti,
    revoke_all_refresh_tokens,
    store_refresh_jti,
)


def test_refresh_jti_one_time_use(monkeypatch):
    redis = MagicMock()
    redis.setex.return_value = True
    redis.delete.side_effect = [1, 0]
    monkeypatch.setattr(
        "services.refresh_token_store.get_redis_connection", lambda: redis
    )
    jti = new_refresh_jti()
    store_refresh_jti(1, jti)
    assert consume_refresh_jti(1, jti) is True
    assert consume_refresh_jti(1, jti) is False


def test_revoke_all_refresh_tokens(monkeypatch):
    redis = MagicMock()
    redis.scan_iter.return_value = [b"refresh:1:a", b"refresh:1:b"]
    monkeypatch.setattr(
        "services.refresh_token_store.get_redis_connection", lambda: redis
    )
    revoke_all_refresh_tokens(1)
    assert redis.delete.call_count == 2
