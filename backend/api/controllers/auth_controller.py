from __future__ import annotations

from fastapi import HTTPException, Request, Response, status

from config import settings
from core.auth_rate_limiter import (
    check_verification_attempts,
    check_verify_rate_limit,
    clear_verification_attempts,
    record_verification_failure,
)
from core.debug_logger import debug_trace, get_logger
from core.roles import is_valid_role
from core.token_version_cache import cache_token_version
from models.user import User
from repositories.audit_repository import AuditRepository
from repositories.user_repository import UserRepository
from schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserContext,
    VerifyEmailRequest,
)
from services.email_verification_service import (
    generate_verification_code,
    hash_verification_code,
    resend_cooldown_message,
    resend_cooldown_remaining_seconds,
    send_verification_code,
    verification_expires_at,
    verify_code,
)
from services.jwt_service import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_refresh_token_version,
)
from services.refresh_token_store import (
    consume_refresh_jti,
    new_refresh_jti,
    revoke_all_refresh_tokens,
    store_refresh_jti,
)
from utils.password_hashing import hash_password, verify_password

logger = get_logger(__name__)


def _cookie_params() -> dict:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }


def _user_auth_flags(user: User) -> tuple[bool, bool]:
    return user.email_verified_at is not None, user.must_change_password


def _login_response(user: User) -> LoginResponse:
    email_verified, must_change_password = _user_auth_flags(user)
    resend_in = (
        0
        if email_verified
        else resend_cooldown_remaining_seconds(user)
    )
    return LoginResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=email_verified,
        must_change_password=must_change_password,
        verification_resend_in_seconds=resend_in,
    )


def set_auth_cookies(response: Response, *, user: User) -> None:
    email_verified, must_change_password = _user_auth_flags(user)
    token_version = int(user.token_version or 1)
    cache_token_version(user.id, token_version)
    jti = new_refresh_jti()
    access = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=email_verified,
        must_change_password=must_change_password,
        token_version=token_version,
    )
    refresh = create_refresh_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=email_verified,
        must_change_password=must_change_password,
        token_version=token_version,
        jti=jti,
    )
    store_refresh_jti(user.id, jti)
    params = _cookie_params()
    response.set_cookie(
        key="access_token",
        value=access,
        max_age=settings.jwt_access_expire_minutes * 60,
        **params,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        max_age=settings.jwt_refresh_expire_days * 24 * 60 * 60,
        **params,
    )


def clear_auth_cookies(response: Response) -> None:
    params = _cookie_params()
    response.delete_cookie(key="access_token", **params)
    response.delete_cookie(key="refresh_token", **params)


class AuthController:
    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    async def _audit_security(
        self,
        user_id: int | None,
        action: str,
        *,
        entity_id: int = 0,
        after: dict | None = None,
    ) -> None:
        if self._audit_repo is None:
            return
        await self._audit_repo.log(
            user_id,
            action,
            "user",
            entity_id,
            None,
            after,
        )

    async def _authenticate(self, email: str, password: str) -> User:
        user = await self._user_repo.find_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            await self._audit_security(
                user.id if user else None,
                "login_failed",
                entity_id=user.id if user else 0,
                after={"email": email.lower()},
            )
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_credentials",
                    "message": "Wrong email or password.",
                },
            )
        if not user.is_active:
            await self._audit_security(
                user.id,
                "login_failed",
                entity_id=user.id,
                after={"reason": "account_disabled"},
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "account_disabled",
                    "message": "This account has been disabled.",
                },
            )
        if not is_valid_role(user.role):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "invalid_role",
                    "message": "User account has an invalid role.",
                },
            )
        return user

    async def login(self, request: LoginRequest, response: Response) -> LoginResponse:
        user = await self._authenticate(request.email, request.password)
        if not user.must_change_password:
            verification_code = generate_verification_code()
            user = await self._user_repo.set_email_verification_code(
                user,
                code_hash=hash_verification_code(verification_code),
                expires_at=verification_expires_at(),
            )
            send_verification_code(user.email, verification_code)
        revoke_all_refresh_tokens(user.id)
        set_auth_cookies(response, user=user)
        await self._audit_security(
            user.id,
            "login_success",
            entity_id=user.id,
        )
        return _login_response(user)

    async def refresh(self, request: Request, response: Response) -> LoginResponse:
        token = request.cookies.get("refresh_token")
        if not token:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "refresh_required",
                    "message": "Session expired. Please sign in again.",
                },
            )

        ctx, jti = decode_refresh_token(token)
        if ctx is None or not jti:
            clear_auth_cookies(response)
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_refresh",
                    "message": "Session expired. Please sign in again.",
                },
            )

        if not consume_refresh_jti(ctx.user_id, jti):
            clear_auth_cookies(response)
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_refresh",
                    "message": "Session expired. Please sign in again.",
                },
            )

        user = await self._user_repo.get(ctx.user_id)
        if not user or not user.is_active or not is_valid_role(user.role):
            clear_auth_cookies(response)
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_refresh",
                    "message": "Session expired. Please sign in again.",
                },
            )

        jwt_version = get_refresh_token_version(token)
        if jwt_version is not None and jwt_version != int(user.token_version or 1):
            clear_auth_cookies(response)
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_refresh",
                    "message": "Session expired. Please sign in again.",
                },
            )

        set_auth_cookies(response, user=user)
        return _login_response(user)

    @debug_trace
    async def logout(self, request: Request, response: Response) -> dict:
        token = request.cookies.get("refresh_token")
        if token:
            ctx, _jti = decode_refresh_token(token)
            if ctx is not None:
                revoke_all_refresh_tokens(ctx.user_id)
        clear_auth_cookies(response)
        return {"message": "Logged out."}

    @debug_trace
    async def me(self, user: UserContext) -> LoginResponse:
        db_user = await self._user_repo.get(user.user_id)
        if db_user is None or not db_user.is_active:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_session",
                    "message": "Session expired. Please sign in again.",
                },
            )
        return _login_response(db_user)

    async def verify_email(
        self,
        user_ctx: UserContext,
        body: VerifyEmailRequest,
        response: Response,
    ) -> LoginResponse:
        check_verify_rate_limit(user_ctx.user_id)
        check_verification_attempts(user_ctx.user_id)

        user = await self._user_repo.get(user_ctx.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_session",
                    "message": "Session expired. Please sign in again.",
                },
            )
        if user.email_verified_at is not None:
            return _login_response(user)
        if user.must_change_password:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "password_change_required",
                    "message": "Change your password before verifying your email.",
                },
            )

        if not verify_code(user, body.code):
            record_verification_failure(user_ctx.user_id)
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_verification_code",
                    "message": (
                        "Invalid or expired verification code. "
                        "Codes expire after 10 minutes."
                    ),
                },
            )

        clear_verification_attempts(user_ctx.user_id)
        user = await self._user_repo.mark_email_verified(user)
        set_auth_cookies(response, user=user)
        return _login_response(user)

    async def resend_verification_code(
        self,
        user_ctx: UserContext,
        response: Response,
    ) -> LoginResponse:
        user = await self._user_repo.get(user_ctx.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_session",
                    "message": "Session expired. Please sign in again.",
                },
            )
        if user.email_verified_at is not None:
            return _login_response(user)
        if user.must_change_password:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "password_change_required",
                    "message": "Change your password before requesting a verification code.",
                },
            )

        wait = resend_cooldown_remaining_seconds(user)
        if wait > 0:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "resend_too_soon",
                    "message": resend_cooldown_message(wait),
                    "retry_after_seconds": wait,
                },
            )

        verification_code = generate_verification_code()
        user = await self._user_repo.set_email_verification_code(
            user,
            code_hash=hash_verification_code(verification_code),
            expires_at=verification_expires_at(),
        )
        clear_verification_attempts(user.id)
        send_verification_code(user.email, verification_code)
        set_auth_cookies(response, user=user)
        return _login_response(user)

    async def change_password(
        self,
        user_ctx: UserContext,
        body: ChangePasswordRequest,
        response: Response,
    ) -> LoginResponse:
        user = await self._user_repo.get(user_ctx.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_session",
                    "message": "Session expired. Please sign in again.",
                },
            )
        if not user.must_change_password:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "password_change_not_required",
                    "message": "Password change is not required for this account.",
                },
            )
        if not verify_password(body.current_password, user.password_hash):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_current_password",
                    "message": "Current password is incorrect.",
                },
            )
        if body.current_password == body.new_password:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "same_password",
                    "message": "New password must be different from the current password.",
                },
            )

        password_hash = hash_password(body.new_password)
        user = await self._user_repo.update_password(user, password_hash)
        await self._user_repo.bump_token_version(user.id)
        user = await self._user_repo.get(user.id)
        assert user is not None
        revoke_all_refresh_tokens(user.id)
        verification_code = generate_verification_code()
        user = await self._user_repo.set_email_verification_code(
            user,
            code_hash=hash_verification_code(verification_code),
            expires_at=verification_expires_at(),
        )
        send_verification_code(user.email, verification_code)
        set_auth_cookies(response, user=user)
        return _login_response(user)
