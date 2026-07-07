from __future__ import annotations

from fastapi import HTTPException, Request, Response, status

from config import settings
from core.debug_logger import debug_trace, get_logger
from core.roles import is_valid_role
from core.token_version_cache import cache_token_version
from models.user import User
from repositories.audit_repository import AuditRepository
from repositories.user_repository import UserRepository
from schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    ResetPasswordRequest,
    UserContext,
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
from services.password_reset_service import (
    FORGOT_PASSWORD_MESSAGE,
    generate_reset_token,
    hash_reset_token,
    reset_cooldown_remaining_seconds,
    reset_expires_at,
    send_password_reset_email,
    verify_reset_token,
)
from utils.password_hashing import hash_password, verify_password

logger = get_logger(__name__)


def _cookie_params() -> dict:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }


def _login_response(user: User) -> LoginResponse:
    return LoginResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        must_change_password=user.must_change_password,
    )


def set_auth_cookies(response: Response, *, user: User) -> None:
    token_version = int(user.token_version or 1)
    cache_token_version(user.id, token_version)
    jti = new_refresh_jti()
    access = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        must_change_password=user.must_change_password,
        token_version=token_version,
    )
    refresh = create_refresh_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        must_change_password=user.must_change_password,
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
        set_auth_cookies(response, user=user)
        return _login_response(user)

    async def forgot_password(
        self,
        body: ForgotPasswordRequest,
    ) -> MessageResponse:
        user = await self._user_repo.find_by_email(body.email)
        if user is None or not user.is_active:
            return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)

        if reset_cooldown_remaining_seconds(user) > 0:
            return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)

        token = generate_reset_token()
        await self._user_repo.set_password_reset_token(
            user,
            token_hash=hash_reset_token(token),
            expires_at=reset_expires_at(),
        )
        await self._audit_security(
            user.id,
            "password_reset_requested",
            entity_id=user.id,
        )
        try:
            send_password_reset_email(user.email, token)
        except Exception:
            logger.exception("Failed to send password reset email for user_id=%d", user.id)
        return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)

    async def reset_password(
        self,
        body: ResetPasswordRequest,
        response: Response,
    ) -> LoginResponse:
        user = await self._user_repo.find_by_email(body.email)
        if user is None or not user.is_active or not verify_reset_token(user, body.token):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_reset_token",
                    "message": "This password reset link is invalid or has expired.",
                },
            )

        password_hash = hash_password(body.new_password)
        user = await self._user_repo.update_password(user, password_hash)
        user = await self._user_repo.clear_password_reset_token(user)
        await self._user_repo.bump_token_version(user.id)
        user = await self._user_repo.get(user.id)
        assert user is not None
        revoke_all_refresh_tokens(user.id)
        set_auth_cookies(response, user=user)
        await self._audit_security(
            user.id,
            "password_reset_completed",
            entity_id=user.id,
        )
        return _login_response(user)
