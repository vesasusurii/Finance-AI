import os
from datetime import datetime, timedelta, timezone

import bcrypt

os.environ["DEBUG"] = "false"

from models.user import User
from services.password_reset_service import (
    FORGOT_PASSWORD_MESSAGE,
    generate_reset_token,
    hash_reset_token,
    reset_cooldown_remaining_seconds,
    reset_expires_at,
    verify_reset_token,
)


def _user(**overrides) -> User:
    base = {
        "id": 1,
        "email": "finance@borek.com",
        "password_hash": "hash",
        "role": "finance",
        "is_active": True,
        "email_verified_at": datetime.now(timezone.utc),
        "must_change_password": False,
        "email_verification_code_hash": None,
        "email_verification_expires_at": None,
        "password_reset_token_hash": None,
        "password_reset_expires_at": None,
        "password_reset_requested_at": None,
        "created_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return User(**base)


def test_verify_reset_token_accepts_valid_token():
    token = generate_reset_token()
    user = _user(
        password_reset_token_hash=hash_reset_token(token),
        password_reset_expires_at=reset_expires_at(),
    )

    assert verify_reset_token(user, token) is True


def test_verify_reset_token_rejects_expired_token():
    token = generate_reset_token()
    user = _user(
        password_reset_token_hash=hash_reset_token(token),
        password_reset_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    assert verify_reset_token(user, token) is False


def test_reset_cooldown_remaining_seconds():
    user = _user(
        password_reset_requested_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )

    assert reset_cooldown_remaining_seconds(user) > 0


def test_forgot_password_message_is_generic():
    assert "account exists" in FORGOT_PASSWORD_MESSAGE.lower()
