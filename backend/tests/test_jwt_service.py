from datetime import timedelta

import jwt

from config import settings
from services.jwt_service import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


def test_access_and_refresh_token_types():
    access = create_access_token(user_id=1, email="a@b.com", role="finance")
    refresh = create_refresh_token(user_id=1, email="a@b.com", role="admin")

    user, err = decode_access_token(access)
    assert err is None
    assert user is not None
    assert user.role == "finance"

    ref_user = decode_refresh_token(refresh)
    assert ref_user is not None
    assert ref_user.role == "admin"

    access_payload = jwt.decode(access, settings.jwt_secret, algorithms=["HS256"])
    refresh_payload = jwt.decode(refresh, settings.jwt_secret, algorithms=["HS256"])
    assert access_payload["type"] == TOKEN_TYPE_ACCESS
    assert refresh_payload["type"] == TOKEN_TYPE_REFRESH


def test_refresh_rejects_access_token():
    access = create_access_token(user_id=1, email="a@b.com", role="finance")
    assert decode_refresh_token(access) is None


def test_expired_access_token():
    token = jwt.encode(
        {
            "user_id": 1,
            "email": "a@b.com",
            "role": "finance",
            "type": TOKEN_TYPE_ACCESS,
            "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            - timedelta(seconds=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    user, err = decode_access_token(token)
    assert user is None
    assert err == "token_expired"
