"""Email verification code generation and validation."""

from __future__ import annotations

import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import bcrypt

from config import settings
from models.user import User

VERIFICATION_CODE_TTL_DAYS = 7


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verification_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=VERIFICATION_CODE_TTL_DAYS)


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
    if settings.environment == "local":
        print(f"[auth] Email verification code for {email}: {code}")


def send_verification_code(email: str, code: str) -> None:
    if not settings.smtp_host:
        log_verification_code_for_local(email, code)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message["Subject"] = "Borek Finance email verification code"
    message.set_content(
        "\n".join(
            [
                "Your Borek Finance verification code is:",
                "",
                code,
                "",
                "This code expires in 7 days.",
            ]
        )
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
