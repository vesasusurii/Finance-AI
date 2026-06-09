"""API-key auth for Outlook / n8n invoice email ingestion."""

import secrets

from fastapi import Depends, Header, HTTPException

from api.dependencies import get_audit_repo, get_user_repo
from config import settings
from core.roles import ROLE_FINANCE
from repositories.audit_repository import AuditRepository
from repositories.user_repository import UserRepository
from schemas.auth import UserContext


async def verify_email_ingest_user(
    x_email_ingest_key: str | None = Header(default=None, alias="X-Email-Ingest-Key"),
    user_repo: UserRepository = Depends(get_user_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> UserContext:
    if not settings.email_ingest_api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "email_ingest_disabled",
                "message": "EMAIL_INGEST_API_KEY is not configured on the server.",
            },
        )

    provided = x_email_ingest_key or ""
    expected = settings.email_ingest_api_key
    if not provided or not secrets.compare_digest(provided, expected):
        await audit_repo.log(
            None,
            "invalid_api_key",
            "email_ingest",
            0,
            None,
            {"header": "X-Email-Ingest-Key"},
        )
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Invalid or missing X-Email-Ingest-Key header.",
            },
        )

    row = await user_repo.find_by_email(settings.email_ingest_user_email)
    if row is None or not row.is_active:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "email_ingest_user_missing",
                "message": (
                    f"No active user found for EMAIL_INGEST_USER_EMAIL="
                    f"{settings.email_ingest_user_email!r}."
                ),
            },
        )

    return UserContext(
        user_id=row.id,
        email=row.email,
        role=row.role if row.role in ("finance", "admin") else ROLE_FINANCE,
        email_verified=row.email_verified_at is not None,
        must_change_password=row.must_change_password,
    )
