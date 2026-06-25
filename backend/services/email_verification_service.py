"""Email verification code generation and validation."""

from __future__ import annotations

import math
import secrets
import smtplib
from datetime import datetime, timedelta, timezone

import bcrypt

from config import settings
from core.debug_logger import get_logger
from models.user import User
from services.verification_email_template import build_verification_email_message

logger = get_logger(__name__)

VERIFICATION_CODE_TTL_MINUTES = 10
VERIFICATION_RESEND_COOLDOWN_MINUTES = 2


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verification_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        minutes=VERIFICATION_CODE_TTL_MINUTES
    )


def verification_code_issued_at(user: User) -> datetime | None:
    """Infer when the current code was sent from its expiry timestamp."""
    if user.email_verification_expires_at is None:
        return None
    expires = user.email_verification_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires - timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES)


def resend_cooldown_remaining_seconds(user: User) -> int:
    """Seconds until the user may request another verification email."""
    if user.email_verified_at is not None:
        return 0
    issued = verification_code_issued_at(user)
    if issued is None:
        return 0
    elapsed = (datetime.now(timezone.utc) - issued).total_seconds()
    cooldown = VERIFICATION_RESEND_COOLDOWN_MINUTES * 60
    remaining = cooldown - elapsed
    return max(0, math.ceil(remaining))


def resend_cooldown_message(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    if minutes and secs:
        return f"You can request a new code in {minutes}m {secs}s."
    if minutes:
        return f"You can request a new code in {minutes} minute{'s' if minutes != 1 else ''}."
    return f"You can request a new code in {secs} seconds."


def verify_code(user: User, code: str) -> bool:
    if not user.email_verification_code_hash:
        return False
    if user.email_verification_expires_at is None:
        return False
    expires = user.email_verification_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return False
    return bcrypt.checkpw(
        code.encode("utf-8"),
        user.email_verification_code_hash.encode("utf-8"),
    )


def log_verification_code_for_local(email: str, code: str) -> None:
    """Local dev without SMTP: codes go to backend logs, not email."""
    if settings.environment != "local":
        return
    if settings.smtp_host and not settings.log_verification_codes:
        return
    logger.info(
        "Email verification code for %s: %s (expires in %s minutes)",
        email,
        code,
        VERIFICATION_CODE_TTL_MINUTES,
    )


def send_verification_code(email: str, code: str) -> None:
    if not settings.smtp_host:
        log_verification_code_for_local(email, code)
        return

    message = build_verification_email_message(
        from_addr=settings.smtp_from_email,
        to_addr=email,
        subject="Your Borek Finance verification code",
        code=code,
        ttl_minutes=VERIFICATION_CODE_TTL_MINUTES,
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
