from datetime import datetime, timedelta, timezone

from models.user import User
from services.email_verification_service import (
    VERIFICATION_CODE_TTL_MINUTES,
    VERIFICATION_RESEND_COOLDOWN_MINUTES,
    resend_cooldown_message,
    resend_cooldown_remaining_seconds,
    verification_code_issued_at,
)


def _user_with_code(*, issued_at: datetime) -> User:
    user = User(
        id=1,
        email="test@example.com",
        password_hash="x",
        role="finance",
        is_active=True,
    )
    user.email_verification_expires_at = issued_at + timedelta(
        minutes=VERIFICATION_CODE_TTL_MINUTES
    )
    user.email_verification_code_hash = "hash"
    return user


def test_verification_code_issued_at_from_expiry():
    issued = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    user = _user_with_code(issued_at=issued)
    assert verification_code_issued_at(user) == issued


def test_resend_cooldown_blocks_for_two_minutes():
    issued = datetime.now(timezone.utc) - timedelta(seconds=30)
    user = _user_with_code(issued_at=issued)
    remaining = resend_cooldown_remaining_seconds(user)
    assert remaining > 0
    assert remaining <= VERIFICATION_RESEND_COOLDOWN_MINUTES * 60


def test_resend_cooldown_allows_after_two_minutes():
    issued = datetime.now(timezone.utc) - timedelta(
        minutes=VERIFICATION_RESEND_COOLDOWN_MINUTES, seconds=1
    )
    user = _user_with_code(issued_at=issued)
    assert resend_cooldown_remaining_seconds(user) == 0


def test_resend_cooldown_message():
    assert "1m 30s" in resend_cooldown_message(90)
